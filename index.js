require("dotenv").config();

const path = require("path");
const https = require("https");

const {
    Client,
    GatewayIntentBits,
    REST,
    Routes,
    SlashCommandBuilder
} = require("discord.js");

const mineflayer = require("mineflayer");

// ==================================================
// CONFIG
// ==================================================

const MC_HOST = "thenexus.aternos.me";
const MC_PORT = 32552;
const MC_VERSION = "26.2";
const MC_USERNAME = "MCLogger";

const MINECRAFT_CHANNEL_ID = process.env.MINECRAFT_CHANNEL_ID;
const BOT_LOG_CHANNEL_ID = process.env.BOT_LOG_CHANNEL_ID;

// ==================================================
// ENVIRONMENT CHECK
// ==================================================

if (!process.env.DISCORD_TOKEN) {
    console.error("❌ DISCORD_TOKEN is missing from .env");
    process.exit(1);
}

if (!process.env.MC_PASSWORD) {
    console.error("❌ MC_PASSWORD is missing from .env");
    process.exit(1);
}

if (!process.env.MINECRAFT_CHANNEL_ID) {
    console.error("❌ MINECRAFT_CHANNEL_ID is missing from .env");
    process.exit(1);
}

if (!process.env.BOT_LOG_CHANNEL_ID) {
    console.error("⚠️ BOT_LOG_CHANNEL_ID is missing from .env");
    console.error("⚠️ Discord diagnostic logs will be disabled.");
}

// ==================================================
// DISCORD CLIENT
// ==================================================

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent
    ]
});

// ==================================================
// PACKAGE VERSION DETECTOR
// ==================================================

function showPackageVersion(pkg) {
    try {
        const pkgPath = require.resolve(`${pkg}/package.json`);
        const pkgJson = require(pkgPath);

        console.log(`📦 ${pkg}: ${pkgJson.version}`);
    } catch {
        console.log(`⚠️ ${pkg}: unable to determine version`);
    }
}

console.log("=================================");
console.log("       PACKAGE VERSIONS");
console.log("=================================");

[
    "mineflayer",
    "prismarine-chat",
    "minecraft-protocol",
    "minecraft-data",
    "prismarine-registry"
].forEach(showPackageVersion);

console.log("=================================");

// ==================================================
// MINECRAFT STATE
// ==================================================

let mcBot = null;

let reconnectTimeout = null;

let afkMovementTimeout = null;
let afkStuckInterval = null;

let afkLastPosition = null;
let afkStillTime = 0;
let afkDirection = "forward";

// ==================================================
// DIAGNOSTIC LOGGING
// ==================================================

async function sendBotLog(message) {
    try {
        if (!BOT_LOG_CHANNEL_ID) return;

        if (!client.isReady()) {
            console.log("⚠️ Discord not ready; diagnostic log skipped.");
            return;
        }

        const channel = await client.channels.fetch(BOT_LOG_CHANNEL_ID);

        if (!channel || !channel.isTextBased()) {
            console.log("⚠️ Bot log channel unavailable.");
            return;
        }

        await channel.send(message);

    } catch (error) {
        console.error(
            "❌ Failed to send diagnostic log:",
            error.message
        );
    }
}

// ==================================================
// DISCORD CHANNEL
// ==================================================

function getMinecraftChannel() {
    if (!MINECRAFT_CHANNEL_ID) {
        console.log("❌ MINECRAFT_CHANNEL_ID is missing.");
        return null;
    }

    const channel = client.channels.cache.get(
        MINECRAFT_CHANNEL_ID
    );

    if (!channel) {
        console.log(
            `❌ Could not find Discord channel ${MINECRAFT_CHANNEL_ID}`
        );

        return null;
    }

    return channel;
}

async function sendToDiscord(message) {
    const channel = getMinecraftChannel();

    if (!channel) return;

    console.log(`[MC → DISCORD] ${message}`);

    try {
        await channel.send(message);

        console.log("✅ Message sent to Discord.");

    } catch (error) {
        console.error(
            "❌ Failed to send message to Discord:",
            error
        );
    }
}

// ==================================================
// SMART AFK MOVEMENT
// ==================================================

const AFK_WALK_TIME = 4 * 60 * 1000;
const STUCK_CHECK_INTERVAL = 1000;
const STUCK_TIME = 3 * 1000;
const TURN_ANGLE = Math.PI / 2;

function stopAfkMovement() {
    if (afkMovementTimeout) {
        clearTimeout(afkMovementTimeout);
        afkMovementTimeout = null;
    }

    if (afkStuckInterval) {
        clearInterval(afkStuckInterval);
        afkStuckInterval = null;
    }

    if (mcBot) {
        try {
            mcBot.clearControlStates();
        } catch {}
    }

    afkLastPosition = null;
    afkStillTime = 0;
}

async function turnAroundSmartly() {
    if (!mcBot || !mcBot.entity) return;

    const bot = mcBot;

    const currentYaw = bot.entity.yaw;
    const newYaw = currentYaw + TURN_ANGLE;

    try {
        bot.clearControlStates();

        await bot.look(
            newYaw,
            bot.entity.pitch,
            true
        );

        if (mcBot !== bot || !bot.entity) return;

        console.log(
            "🧠 Smart AFK: obstacle detected, turning 90°."
        );

        bot.setControlState(
            afkDirection,
            true
        );

    } catch (error) {
        console.error(
            "❌ Smart AFK turn failed:",
            error
        );

        sendBotLog(
            `❌ **Smart AFK turn failed**\n\`\`\`\n${String(
                error.stack || error
            ).slice(0, 1800)}\n\`\`\``
        );
    }
}

function startAfkMovement() {
    stopAfkMovement();

    if (!mcBot || !mcBot.entity) {
        console.log(
            "⚠️ Smart AFK could not start: Minecraft bot unavailable."
        );

        return;
    }

    console.log(
        "🕒 Smart AFK movement system started."
    );

    afkDirection = "forward";

    function startWalking() {
        if (!mcBot || !mcBot.entity) return;

        const bot = mcBot;

        bot.clearControlStates();

        bot.setControlState(
            afkDirection,
            true
        );

        console.log(
            `🚶 Smart AFK: walking ${afkDirection} for 4 minutes.`
        );

        afkLastPosition =
            bot.entity.position.clone();

        afkStillTime = 0;

        if (afkStuckInterval) {
            clearInterval(afkStuckInterval);
        }

        afkStuckInterval = setInterval(() => {
            if (!mcBot || mcBot !== bot || !bot.entity) {
                return;
            }

            const currentPosition =
                bot.entity.position;

            if (!afkLastPosition) {
                afkLastPosition =
                    currentPosition.clone();

                return;
            }

            const distance =
                currentPosition.distanceTo(
                    afkLastPosition
                );

            if (distance < 0.03) {
                afkStillTime +=
                    STUCK_CHECK_INTERVAL;

                if (afkStillTime >= STUCK_TIME) {
                    console.log(
                        "🧱 Smart AFK: MC Logger is stuck!"
                    );

                    afkStillTime = 0;

                    turnAroundSmartly();
                }

            } else {
                afkStillTime = 0;
            }

            afkLastPosition =
                currentPosition.clone();

        }, STUCK_CHECK_INTERVAL);

        if (afkMovementTimeout) {
            clearTimeout(afkMovementTimeout);
        }

        afkMovementTimeout = setTimeout(() => {
            if (!mcBot || mcBot !== bot) return;

            bot.clearControlStates();

            console.log(
                `⏹️ Smart AFK: ${afkDirection} phase finished.`
            );

            afkDirection =
                afkDirection === "forward"
                    ? "back"
                    : "forward";

            startWalking();

        }, AFK_WALK_TIME);
    }

    startWalking();
}

// ==================================================
// MINECRAFT CONNECTION
// ==================================================

function connectMinecraft() {
    if (mcBot) {
        console.log(
            "⚠️ Minecraft bot already exists."
        );

        return;
    }

    console.log(
        "🔌 Connecting to Minecraft..."
    );

    sendBotLog(
        "🔌 **MC Logger is connecting to Minecraft...**"
    );

    const bot = mineflayer.createBot({
        host: MC_HOST,
        port: MC_PORT,
        username: MC_USERNAME,
        auth: "offline",
        version: MC_VERSION,
        checkTimeoutInterval: 60000
    });

    mcBot = bot;

    // ==================================================
    // TEAM PACKET DEBUG
    // ==================================================

    bot._client.on(
        "packet",
        (data, meta) => {
            if (meta.name === "team") {
                console.log(
                    "🚨 TEAM PACKET RECEIVED:"
                );

                console.log(
                    JSON.stringify(
                        data,
                        null,
                        2
                    )
                );
            }
        }
    );

    // ==================================================
    // LOGIN
    // ==================================================

    bot.once("login", () => {
        console.log(
            "🟢 Minecraft login successful!"
        );

        sendBotLog(
            "🟢 **Minecraft login successful.**"
        );
    });

    // ==================================================
    // SPAWN
    // ==================================================

    bot.once("spawn", () => {
        console.log(
            "🟢 MC Logger spawned in Minecraft!"
        );

        sendBotLog(
            "🟢 **MC Logger spawned and connected to Minecraft.**"
        );

        setTimeout(() => {
            if (mcBot !== bot) return;

            console.log(
                "🔐 Logging into LoginSecurity..."
            );

            bot.chat(
                `/login ${process.env.MC_PASSWORD}`
            );

            startAfkMovement();

        }, 2000);
    });

    // ==================================================
    // PLAYER CHAT
    // ==================================================

    bot.on(
        "chat",
        (username, message) => {
            if (username === bot.username) return;

            console.log(
                `[MC CHAT] ${username}: ${message}`
            );
        }
    );

    // ==================================================
    // FULL MINECRAFT MESSAGE STREAM
    // ==================================================

    bot.on(
        "messagestr",
        (message) => {
            if (!message || !message.trim()) {
                return;
            }

            console.log(
                `[MC CHAT LOG] ${message}`
            );

            if (message.includes("MCLogger")) {
                return;
            }

            sendToDiscord(message);
        }
    );

    // ==================================================
    // PLAYER JOIN
    // ==================================================

    bot.on(
        "playerJoined",
        player => {
            if (!player || !player.username) {
                return;
            }

            console.log(
                `🟢 Player joined: ${player.username}`
            );

            sendToDiscord(
                `🟢 **${player.username} joined the Minecraft server.**`
            );
        }
    );

    // ==================================================
    // PLAYER LEAVE
    // ==================================================

    bot.on(
        "playerLeft",
        player => {
            if (!player || !player.username) {
                return;
            }

            console.log(
                `🔴 Player left: ${player.username}`
            );

            sendToDiscord(
                `🔴 **${player.username} left the Minecraft server.**`
            );
        }
    );

    // ==================================================
    // BOT DEATH
    // ==================================================

    bot.on(
        "death",
        () => {
            console.log(
                "💀 MC Logger died."
            );

            sendToDiscord(
                "💀 **MC Logger died.**"
            );

            sendBotLog(
                "💀 **MC Logger died in Minecraft.**"
            );
        }
    );

    // ==================================================
    // MINECRAFT ERROR
    // ==================================================

    bot.on(
        "error",
        error => {
            console.error(
                "❌ Minecraft ERROR:"
            );

            console.error(error);

            sendBotLog(
                `❌ **Minecraft error**\n\`\`\`\n${String(
                    error.stack || error
                ).slice(0, 1800)}\n\`\`\``
            );
        }
    );

    // ==================================================
    // KICK
    // ==================================================

    bot.on(
        "kicked",
        (reason, loggedIn) => {
            let reasonText;

            try {
                reasonText =
                    typeof reason === "string"
                        ? reason
                        : JSON.stringify(
                            reason,
                            null,
                            2
                        );
            } catch {
                reasonText =
                    String(reason);
            }

            console.error(
                "🚫 Minecraft KICKED:"
            );

            console.error(
                reasonText
            );

            sendBotLog(
                `🚫 **MC Logger was kicked from Minecraft.**\n` +
                `**Logged in:** ${loggedIn}\n` +
                `**Reason:**\n\`\`\`\n${reasonText.slice(
                    0,
                    1600
                )}\n\`\`\``
            );
        }
    );

    // ==================================================
    // CONNECTION END
    // ==================================================

    bot.on(
        "end",
        reason => {
            console.log(
                "🔴 Minecraft connection ended:",
                reason
            );

            console.log(
                "Minecraft bot state:",
                bot._client?.state
            );

            sendBotLog(
                `🔴 **Minecraft connection ended.**\n` +
                `Reason: \`${String(
                    reason || "unknown"
                ).slice(0, 500)}\``
            );

            stopAfkMovement();

            if (mcBot === bot) {
                mcBot = null;
            }

            if (reconnectTimeout) {
                return;
            }

            console.log(
                "🔄 Reconnecting to Minecraft in 5 seconds..."
            );

            sendBotLog(
                "🔄 **MC Logger will reconnect to Minecraft in 5 seconds.**"
            );

            reconnectTimeout =
                setTimeout(() => {
                    reconnectTimeout = null;

                    connectMinecraft();

                }, 5000);
        }
    );
}

// ==================================================
// DISCORD → MINECRAFT
// ==================================================

client.on(
    "messageCreate",
    message => {
        if (message.author.bot) return;

        console.log(
            `[DISCORD] #${message.channel.name}: ` +
            `${message.author.username}: ` +
            `${message.content}`
        );

        if (
            message.channel.id !==
            MINECRAFT_CHANNEL_ID
        ) {
            return;
        }

        if (!mcBot) {
            console.log(
                "⚠️ Minecraft bot is offline."
            );

            message.reply(
                "🔴 Minecraft bot is currently offline."
            ).catch(() => {});

            return;
        }

        const content =
            message.content.trim();

        if (!content) return;

        const text =
            content.slice(0, 200);

        console.log(
            `[DISCORD → MC] ${message.author.username}: ${text}`
        );

        try {
            mcBot.chat(
                `[Discord] ${message.author.username}: ${text}`
            );

        } catch (error) {
            console.error(
                "❌ Failed to send Discord message to Minecraft:"
            );

            console.error(error);

            sendBotLog(
                `❌ **Discord → Minecraft failed**\n\`\`\`\n${String(
                    error.stack || error
                ).slice(0, 1800)}\n\`\`\``
            );
        }
    }
);

// ==================================================
// SLASH COMMANDS
// ==================================================

const commands = [
    new SlashCommandBuilder()
        .setName("ping")
        .setDescription(
            "Check whether MC Logger is responding."
        ),

    new SlashCommandBuilder()
        .setName("status")
        .setDescription(
            "Show the current Minecraft bot status."
        ),

    new SlashCommandBuilder()
        .setName("help")
        .setDescription(
            "Show MC Logger commands."
        )

].map(
    command => command.toJSON()
);

// ==================================================
// REGISTER SLASH COMMANDS
// ==================================================

async function registerCommands() {
    const rest =
        new REST({ version: "10" })
            .setToken(
                process.env.DISCORD_TOKEN
            );

    try {
        console.log(
            "🧹 Clearing old global slash commands..."
        );

        await rest.put(
            Routes.applicationCommands(
                client.user.id
            ),
            {
                body: []
            }
        );

        console.log(
            "✅ Old global commands cleared."
        );

        const guild =
            client.guilds.cache.first();

        if (!guild) {
            console.log(
                "❌ Bot is not in any Discord server."
            );

            return;
        }

        console.log(
            `⚙️ Registering commands in: ${guild.name}`
        );

        await rest.put(
            Routes.applicationGuildCommands(
                client.user.id,
                guild.id
            ),
            {
                body: commands
            }
        );

        console.log(
            "✅ Slash commands registered."
        );

    } catch (error) {
        console.error(
            "❌ Failed to register slash commands:"
        );

        console.error(error);

        sendBotLog(
            `❌ **Slash command registration failed**\n\`\`\`\n${String(
                error.stack || error
            ).slice(0, 1800)}\n\`\`\``
        );
    }
}

// ==================================================
// SLASH COMMAND HANDLER
// ==================================================

client.on("interactionCreate", async interaction => {
    if (!interaction.isChatInputCommand()) {
        return;
    }

    if (interaction.commandName === "ping") {
        await interaction.reply("🏓 Pong!");
        return;
    }

    if (interaction.commandName === "status") {
        await interaction.reply(
            mcBot
                ? "🟢 **Minecraft:** Online\n🟢 **Discord:** Online"
                : "🔴 **Minecraft:** Offline\n🟢 **Discord:** Online"
        );

        return;
    }

    if (interaction.commandName === "help") {
        await interaction.reply(
            "**MC Logger commands**\n\n" +
            "🏓 `/ping` — Check bot response\n" +
            "📊 `/status` — Show Minecraft status\n" +
            "❓ `/help` — Show available commands"
        );

        return;
    }
});

// ==================================================
// DISCORD READY
// ==================================================

client.once("clientReady", async () => {
    console.log(
        `🟢 Discord logged in as ${client.user.tag}`
    );

    await sendBotLog(
        `🟢 **Discord connected as ${client.user.tag}.**`
    );

    await registerCommands();

    // Start Minecraft after Discord is ready
    connectMinecraft();
});

// ==================================================
// DISCORD ERROR HANDLING
// ==================================================

client.on("error", error => {
    console.error("❌ Discord ERROR:");
    console.error(error);

    sendBotLog(
        `❌ **Discord error**\n\`\`\`\n${String(
            error.stack || error
        ).slice(0, 1800)}\n\`\`\``
    );
});

client.on("warn", warning => {
    console.warn(
        "⚠️ Discord warning:",
        warning
    );

    sendBotLog(
        `⚠️ **Discord warning:** ${String(
            warning
        ).slice(0, 1500)}`
    );
});

// ==================================================
// PROCESS ERROR HANDLING
// ==================================================

process.on("uncaughtExceptionMonitor", error => {
    console.error(
        "💥 Uncaught exception:"
    );

    console.error(error);

    sendBotLog(
        `💥 **Uncaught exception**\n\`\`\`\n${String(
            error.stack || error
        ).slice(0, 1800)}\n\`\`\``
    );
});

process.on("unhandledRejection", reason => {
    console.error(
        "💥 Unhandled promise rejection:"
    );

    console.error(reason);

    sendBotLog(
        `💥 **Unhandled promise rejection**\n\`\`\`\n${String(
            reason?.stack || reason
        ).slice(0, 1800)}\n\`\`\``
    );
});

// ==================================================
// START DISCORD
// ==================================================

console.log(
    "🌐 Starting Discord Gateway connection..."
);

client.login(process.env.DISCORD_TOKEN)
    .then(() => {
        console.log(
            "🔌 Discord login initiated."
        );
    })
    .catch(error => {
        console.error(
            "❌ Discord login failed:"
        );

        console.error(error);
    });