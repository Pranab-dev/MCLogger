require("dotenv").config();

const path = require("path");

function showPackageVersion(pkg) {
    try {
        const pkgPath = require.resolve(`${pkg}/package.json`);
        const pkgJson = require(pkgPath);
        console.log(`📦 ${pkg}: ${pkgJson.version}`);
    } catch (err) {
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

// ==================================================
// DISCORD
// ==================================================

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent
    ]
});

// ==================================================
// MINECRAFT STATE
// ==================================================

let mcBot = null;

let afkInterval = null;
let afkStopTimeout = null;
let reconnectTimeout = null;

// ==================================================
// DISCORD CHANNEL
// ==================================================

function getMinecraftChannel() {
    if (!MINECRAFT_CHANNEL_ID) {
        console.log("❌ MINECRAFT_CHANNEL_ID is missing.");
        return null;
    }

    const channel = client.channels.cache.get(MINECRAFT_CHANNEL_ID);

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
        console.error("❌ Failed to send message to Discord:");
        console.error(error);
    }
}

// ==================================================
// AFK MOVEMENT
// ==================================================

function stopAfkMovement() {
    if (afkInterval) {
        clearInterval(afkInterval);
        afkInterval = null;
    }

    if (afkStopTimeout) {
        clearTimeout(afkStopTimeout);
        afkStopTimeout = null;
    }

    if (mcBot) {
        try {
            mcBot.setControlState("forward", false);
            mcBot.setControlState("back", false);
        } catch {}
    }
}

function startAfkMovement(bot) {
    stopAfkMovement();

    console.log("🕒 AFK movement system started.");

    const runMovementCycle = () => {
        if (!mcBot || mcBot !== bot) return;

        console.log("🚶 AFK: moving forward for 4 minutes.");

        try {
            bot.setControlState("back", false);
            bot.setControlState("forward", true);
        } catch (error) {
            console.error("❌ Forward movement failed:", error);
            return;
        }

        afkStopTimeout = setTimeout(() => {
            if (!mcBot || mcBot !== bot) return;

            console.log("🔙 AFK: moving backward for 4 minutes.");

            try {
                bot.setControlState("forward", false);
                bot.setControlState("back", true);
            } catch (error) {
                console.error("❌ Backward movement failed:", error);
                return;
            }

            afkStopTimeout = setTimeout(() => {
                if (!mcBot || mcBot !== bot) return;

                try {
                    bot.setControlState("back", false);
                    bot.setControlState("forward", false);
                } catch {}

                console.log("🛑 AFK movement cycle finished.");

                afkStopTimeout = null;
            }, 4 * 60 * 1000);

        }, 4 * 60 * 1000);
    };

    afkInterval = setInterval(
        runMovementCycle,
        10 * 60 * 1000
    );
}

// ==================================================
// MINECRAFT CONNECTION
// ==================================================

function connectMinecraft() {
    if (mcBot) {
        console.log("⚠️ Minecraft bot already exists.");
        return;
    }

    console.log("🔌 Connecting to Minecraft...");

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
// DEBUG: MINECRAFT TEAM PACKETS
// ==================================================

bot._client.on("packet", (data, meta) => {
    if (meta.name === "team") {
        console.log("🚨 TEAM PACKET RECEIVED:");
        console.log(JSON.stringify(data, null, 2));
    }
});

    // ==================================================
    // LOGIN
    // ==================================================

    bot.once("login", () => {
        console.log("🟢 Minecraft login successful!");
    });

    // ==================================================
    // SPAWN
    // ==================================================

    bot.once("spawn", () => {
        console.log("🟢 MC Logger spawned in Minecraft!");

        setTimeout(() => {
            if (mcBot !== bot) return;

            console.log("🔐 Logging into LoginSecurity...");

            bot.chat(`/login ${process.env.MC_PASSWORD}`);

            startAfkMovement(bot);
        }, 2000);
    });

// ================================
// MINECRAFT CHAT LOG
// ================================

// Normal player chat — terminal only.
// We don't forward this separately because messagestr also receives it.
bot.on("chat", (username, message) => {
    if (username === bot.username) return;

    console.log(`[MC CHAT] ${username}: ${message}`);
});

// Full Minecraft message stream → Discord
bot.on("messagestr", (message, position) => {
    if (!message || !message.trim()) return;

    console.log(`[MC CHAT LOG] ${message}`);

    // Ignore messages generated by MC Logger itself
    if (message.includes("MCLogger")) return;

    // Send the complete Minecraft message to Discord
    sendToDiscord(`${message}`);
});

    // ==================================================
    // ALL MINECRAFT MESSAGES
    // ==================================================

    bot.on("messagestr", message => {
        console.log(`[MC] ${message}`);
    });

    // ==================================================
    // PLAYER JOIN
    // ==================================================

    bot.on("playerJoined", player => {
        if (!player || !player.username) return;

        console.log(`🟢 Player joined: ${player.username}`);

        sendToDiscord(
            `🟢 **${player.username} joined the Minecraft server.**`
        );
    });

    // ==================================================
    // PLAYER LEAVE
    // ==================================================

    bot.on("playerLeft", player => {
        if (!player || !player.username) return;

        console.log(`🔴 Player left: ${player.username}`);

        sendToDiscord(
            `🔴 **${player.username} left the Minecraft server.**`
        );
    });

    // ==================================================
    // BOT DEATH
    // ==================================================

    bot.on("death", () => {
        console.log("💀 MC Logger died.");

        sendToDiscord(
            "💀 **MC Logger died.**"
        );
    });

    // ==================================================
    // ERROR
    // ==================================================

    bot.on("error", error => {
        console.error("❌ Minecraft ERROR:");
        console.error(error);
    });

    // ==================================================
    // KICK
    // ==================================================

    bot.on("kicked", reason => {
        console.error("❌ Minecraft KICKED:");

        try {
            console.error(JSON.stringify(reason, null, 2));
        } catch {
            console.error(reason);
        }
    });

    // ==================================================
    // CONNECTION END
    // ==================================================

    bot.on("end", reason => {
        console.log("🔴 Minecraft connection ended:", reason);
        console.log("Minecraft bot state:", bot._client?.state);

        stopAfkMovement();

        if (mcBot === bot) {
            mcBot = null;
        }

        if (reconnectTimeout) return;

        console.log("🔄 Reconnecting to Minecraft in 5 seconds...");

        reconnectTimeout = setTimeout(() => {
            reconnectTimeout = null;
            connectMinecraft();
        }, 5000);
    });
}

// ==================================================
// DISCORD → MINECRAFT
// ==================================================

client.on("messageCreate", message => {
    if (message.author.bot) return;

    console.log(
        `[DISCORD] #${message.channel.name}: ${message.author.username}: ${message.content}`
    );

    if (message.channel.id !== MINECRAFT_CHANNEL_ID) return;

    if (!mcBot) {
        console.log("⚠️ Minecraft bot is offline.");

        message.reply("🔴 Minecraft bot is currently offline.")
            .catch(() => {});

        return;
    }

    const content = message.content.trim();

    if (!content) return;

    const text = content.slice(0, 200);

    console.log(
        `[DISCORD → MC] ${message.author.username}: ${text}`
    );

    try {
        mcBot.chat(
            `[Discord] ${message.author.username}: ${text}`
        );
    } catch (error) {
        console.error("❌ Failed to send Discord message to Minecraft:");
        console.error(error);
    }
});

// ==================================================
// SLASH COMMANDS
// ==================================================

const commands = [
    new SlashCommandBuilder()
        .setName("ping")
        .setDescription("Check whether MC Logger is responding."),

    new SlashCommandBuilder()
        .setName("status")
        .setDescription("Show the current Minecraft bot status."),

    new SlashCommandBuilder()
        .setName("help")
        .setDescription("Show MC Logger commands.")
].map(command => command.toJSON());

// ==================================================
// REGISTER SLASH COMMANDS
// ==================================================

async function registerCommands() {
    const rest = new REST({ version: "10" })
        .setToken(process.env.DISCORD_TOKEN);

    try {
        console.log("🧹 Clearing old global slash commands...");

        await rest.put(
            Routes.applicationCommands(client.user.id),
            {
                body: []
            }
        );

        console.log("✅ Old global commands cleared.");

        const guild = client.guilds.cache.first();

        if (!guild) {
            console.log("❌ Bot is not in any Discord server.");
            return;
        }

        console.log(`⚙️ Registering commands in: ${guild.name}`);

        await rest.put(
            Routes.applicationGuildCommands(
                client.user.id,
                guild.id
            ),
            {
                body: commands
            }
        );

        console.log("✅ Slash commands registered.");
    } catch (error) {
        console.error("❌ Failed to register slash commands:");
        console.error(error);
    }
}

// ==================================================
// SLASH COMMAND HANDLER
// ==================================================

client.on("interactionCreate", async interaction => {
    if (!interaction.isChatInputCommand()) return;

    if (interaction.commandName === "ping") {
        await interaction.reply(
            "🏓 Pong!"
        );
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
    }
});

// ==================================================
// DISCORD READY
// ==================================================

client.once("clientReady", async () => {
    console.log("=================================");
    console.log("          MC LOGGER");
    console.log("=================================");
    console.log(`Discord: ${client.user.tag}`);
    console.log("🟢 DISCORD BOT IS ONLINE");

    client.user.setPresence({
        activities: [
            {
                name: "Playing Nexus SMP!",
                type: 0
            }
        ],
        status: "online"
    });

    await registerCommands();

    connectMinecraft();
});

// ==================================================
// DISCORD ERRORS
// ==================================================

client.on("error", (error) => {
    console.error("❌ DISCORD ERROR:", error);
});

client.on("warn", (info) => {
    console.warn("⚠️ DISCORD WARNING:", info);
});

console.log("🌐 Starting Discord Gateway connection...");

setTimeout(() => {
    console.log("⏱️ 15 seconds passed.");
    console.log("Discord ready:", client.isReady());
    console.log("Discord status:", client.ws.status);
}, 15000);

const https = require("https");

console.log("🌐 Testing Discord HTTPS...");

https.get("https://discord.com/api/v10/gateway", (res) => {
    console.log("HTTP status:", res.statusCode);
    console.log("Retry-After:", res.headers["retry-after"]);
    console.log("RateLimit-Remaining:", res.headers["x-ratelimit-remaining"]);
    console.log("RateLimit-Scope:", res.headers["x-ratelimit-scope"]);

    let body = "";

    res.on("data", chunk => {
        body += chunk;
    });

    res.on("end", () => {
        console.log("Response:", body);
    });
}).on("error", error => {
    console.error("❌ HTTPS error:", error);
});

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

// ==================================================
// START
// ==================================================

console.log("🔑 Discord token found.");
console.log("🔌 Connecting to Discord...");

client.login(process.env.DISCORD_TOKEN)
    .then(() => {
        console.log("✅ client.login() completed");
    })
    .catch((error) => {
        console.error("❌ LOGIN FAILED:", error);
    });