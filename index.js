require("dotenv").config();

const fs = require("node:fs");
const path = require("node:path");

const {
    Client,
    Collection,
    GatewayIntentBits
} = require("discord.js");

const mineflayer = require("mineflayer");

// =========================
// DISCORD
// =========================

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent
    ]
});

client.commands = new Collection();

const commandsPath = path.join(__dirname, "commands");
const commandFiles = fs.readdirSync(commandsPath)
    .filter(file => file.endsWith(".js"));

for (const file of commandFiles) {
    const filePath = path.join(commandsPath, file);
    const command = require(filePath);

    client.commands.set(command.data.name, command);
}

// =========================
// MINECRAFT
// =========================

let mcBot = null;
let mcConnected = false;
let connecting = false;

const MC_HOST = "thenexus.aternos.me";
const MC_PORT = 32552;

async function sendToDiscord(message) {
    try {
        const channel = await client.channels.fetch(
            process.env.MINECRAFT_CHANNEL_ID
        );

        if (!channel) return;

        await channel.send(message);
    } catch (error) {
        console.error(
            "Failed to send message to Discord:",
            error.message
        );
    }
}

function connectMinecraft() {
    if (connecting || mcBot) return;

    connecting = true;

    console.log("Trying to connect to Minecraft...");

    const bot = mineflayer.createBot({
        host: MC_HOST,
        port: MC_PORT,
        username: "MCLogger",
        version: false
    });

    mcBot = bot;

    // =========================
    // CONNECTION
    // =========================

    bot.once("login", () => {
        console.log("Minecraft login successful! 🟢");
    });

    bot.once("spawn", () => {
        console.log("MC Logger joined Minecraft! 🟢");

        mcConnected = true;
        connecting = false;

        setTimeout(() => {
            if (!mcBot || mcBot !== bot) return;

            console.log("Logging into LoginSecurity...");

            bot.chat(`/login ${process.env.MC_PASSWORD}`);
        }, 2000);
    });

    // =========================
    // PUBLIC MINECRAFT ACTIVITY
    // =========================

    bot.on("messagestr", async (message) => {
    console.log(`[MC MESSAGE] ${message}`);

    if (!message.trim()) return;

    // Don't forward MC Logger's own messages
    if (message.includes("<MCLogger>")) return;

    await sendToDiscord(`**[MC]** ${message}`);
});

    // =========================
    // PLAYER JOIN
    // =========================

    bot.on("playerJoined", async (player) => {
        console.log(`[MC JOIN] ${player.username}`);

        // Avoid announcing MC Logger itself
        if (player.username === bot.username) return;

        await sendToDiscord(
            `🟢 **${player.username} joined the game**`
        );
    });

    // =========================
    // PLAYER LEAVE
    // =========================

    bot.on("playerLeft", async (player) => {
        console.log(`[MC LEAVE] ${player.username}`);

        if (player.username === bot.username) return;

        await sendToDiscord(
            `🔴 **${player.username} left the game**`
        );
    });

    // =========================
    // KICK
    // =========================

    bot.on("kicked", reason => {
        console.log("MC Logger was kicked.");
        console.log(JSON.stringify(reason, null, 2));
    });

    // =========================
    // ERROR
    // =========================

    bot.on("error", error => {
        console.log(
            "Minecraft connection error:",
            error.message
        );
    });

    // =========================
    // CONNECTION END
    // =========================

    bot.on("end", reason => {
        console.log(
            "Minecraft connection ended:",
            reason
        );

        mcConnected = false;
        connecting = false;

        if (mcBot === bot) {
            mcBot = null;
        }

        console.log(
            "Minecraft server may be offline."
        );

        console.log(
            "Will try again in 5 seconds..."
        );
    });
}

// =========================
// AUTOMATIC RECONNECT
// =========================

setInterval(() => {
    if (!mcBot && !connecting) {
        connectMinecraft();
    }
}, 5000);

// Initial connection
connectMinecraft();

// =========================
// DISCORD READY
// =========================

client.once("clientReady", () => {
    client.user.setPresence({
        activities: [
            {
                name: "Playing Nexus SMP!",
                type: 0
            }
        ],
        status: "online"
    });

    console.log(`MC Logger is online as ${client.user.tag}`);
});

// =========================
// SLASH COMMANDS
// =========================

client.on("interactionCreate", async interaction => {
    if (!interaction.isChatInputCommand()) return;

    const command = client.commands.get(
        interaction.commandName
    );

    if (!command) return;

    try {
        await command.execute(interaction);
    } catch (error) {
        console.error(error);

        if (
            interaction.replied ||
            interaction.deferred
        ) {
            await interaction.followUp({
                content:
                    "There was an error running that command.",
                ephemeral: true
            });
        } else {
            await interaction.reply({
                content:
                    "There was an error running that command.",
                ephemeral: true
            });
        }
    }
});

// =========================
// DISCORD → MINECRAFT
// =========================

client.on("messageCreate", message => {
    if (message.author.bot) return;

    if (
        message.channel.id !==
        process.env.MINECRAFT_CHANNEL_ID
    ) {
        return;
    }

    if (!mcBot || !mcConnected) {
        console.log(
            "[DISCORD → MC] Minecraft is offline. Message not sent."
        );
        return;
    }

    const text = message.content.trim();

    if (!text) return;

    console.log(
        `[DISCORD → MC] ${message.author.username}: ${text}`
    );

    mcBot.chat(
        `[Discord] ${message.author.username}: ${text}`
    );
});

// =========================
// START DISCORD
// =========================

client.login(process.env.DISCORD_TOKEN);