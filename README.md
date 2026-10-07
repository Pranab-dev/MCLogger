# MC Logger

**MC Logger** is a Discord ↔ Minecraft bridge bot built with **Node.js**, **discord.js**, and **Mineflayer**.

It connects a Discord server with a Minecraft Java Edition server, allowing Minecraft activity and chat to be relayed to Discord while providing commands and automated AFK movement.

> **Current Minecraft target:** Java Edition 26.2
> **Protocol:** 776
> **Runtime:** Node.js 22+

---

## ✨ Features

* 💬 **Minecraft → Discord chat bridge**
* 📡 **Discord → Minecraft message bridge**
* 👋 Player join and leave notifications
* ☠️ Player death notifications
* 🔐 Automatic LoginSecurity authentication
* 🔄 Automatic Minecraft reconnection
* 🧠 **Smart AFK movement**

  * Walks automatically without manual input
  * Detects when the bot becomes stuck
  * Automatically turns when an obstacle stops movement
  * Continues moving instead of standing against a wall
* 🤖 Discord slash commands
* 📊 Minecraft connection/status reporting
* 🛡️ Environment-variable based secret configuration
* ☁️ Designed to run on Node.js hosting platforms

---

## 🧩 How It Works

MC Logger acts as a bridge between Discord and Minecraft.

```text
              ┌─────────────────────┐
              │      Discord        │
              │                     │
              │  #minecraft channel │
              └──────────┬──────────┘
                         │
                         │ Discord.js
                         │
                  ┌──────▼──────┐
                  │  MC Logger  │
                  │   Node.js   │
                  └──────┬──────┘
                         │
                         │ Mineflayer
                         │
                  ┌──────▼──────┐
                  │  Minecraft  │
                  │ Java Server │
                  └─────────────┘
```

Messages sent in the configured Discord Minecraft channel can be sent to the Minecraft server.

Minecraft chat can be forwarded back to Discord.

---

## 🛠️ Tech Stack

| Technology                        | Purpose                            |
| --------------------------------- | ---------------------------------- |
| Node.js                           | Runtime                            |
| discord.js                        | Discord API and bot functionality  |
| Mineflayer                        | Minecraft bot client               |
| Complexity-ML Mineflayer 26.2     | Minecraft 26.2 compatibility       |
| dotenv                            | Environment variable configuration |
| Aternos / other Minecraft hosting | Server hosting                     |

---

## 📋 Requirements

Before running MC Logger, make sure you have:

* **Node.js 22 or newer**
* A Discord bot
* A Discord server where the bot can operate
* A Minecraft Java Edition server
* Minecraft **26.2** compatibility
* A Minecraft account/server setup that allows the bot to connect
* LoginSecurity credentials if the server requires `/login`

---

## 📥 Installation

Clone the repository:

```bash
git clone https://github.com/Pranab-dev/MCLogger.git
cd MCLogger
```

Install dependencies:

```bash
npm install
```

Then create a `.env` file in the project root.

---

## 🔐 Environment Variables

Create:

```text
.env
```

Add the required configuration:

```env
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN
MINECRAFT_CHANNEL_ID=YOUR_DISCORD_CHANNEL_ID
MC_PASSWORD=YOUR_MINECRAFT_LOGIN_PASSWORD
```

### Important

Never commit `.env` to GitHub.

Your Discord token and Minecraft password should remain private.

A recommended `.gitignore` entry is:

```gitignore
.env
node_modules/
```

---

## 🤖 Discord Bot Setup

Create a Discord application and bot, then invite it to your server with the permissions required by the project.

MC Logger uses Discord message content, so the appropriate **Message Content Intent** must be enabled for the bot.

The bot uses:

* Guild access
* Guild messages
* Message content
* Slash commands

---

## ⛏️ Minecraft Configuration

MC Logger is currently configured for:

```text
Minecraft Java Edition: 26.2
Protocol: 776
Authentication: offline
```

The bot connects using Mineflayer and automatically handles the LoginSecurity authentication flow.

The Minecraft connection is configured in `index.js`.

Do not place passwords directly into the source code. Use `.env` instead.

---

# 💬 Discord ↔ Minecraft Bridge

## Minecraft → Discord

Minecraft messages can be forwarded to the configured Discord channel.

Examples include:

```text
Player joined the Minecraft server.
Player left the Minecraft server.
Player died.
Minecraft chat messages.
```

System messages can also appear in the Discord bridge depending on what the Minecraft server sends.

---

## Discord → Minecraft

Messages sent in the configured Minecraft Discord channel can be forwarded into Minecraft.

This allows players using Minecraft and Discord to communicate without switching between applications.

---

# 🧠 Smart AFK Movement

MC Logger includes an automated AFK movement system designed to keep the bot active on the Minecraft server.

Instead of simply holding a movement key indefinitely, the bot monitors its position while walking.

### Movement behavior

The system follows a repeating movement cycle:

```text
Wait
  ↓
Walk forward
  ↓
Detect movement
  ↓
If stuck → turn
  ↓
Continue walking
  ↓
Movement phase ends
  ↓
Walk backward
  ↓
Detect movement
  ↓
If stuck → turn
  ↓
Continue walking
  ↓
Repeat
```

### Stuck detection

If MC Logger's position stops changing for several seconds while it is supposed to be moving, the bot considers itself stuck.

For example:

```text
MC Logger
    │
    │ W
    ▼
████████████
    🧱
    │
    │ detects no movement
    ▼
    ↪️ turns
    │
    ▼
continues walking
```

This prevents the bot from spending an entire movement phase permanently pushing against the same wall.

### Why this exists

Normal Mineflayer movement does not always reproduce the exact wall-sliding behavior of a human Minecraft player, especially on newer Minecraft versions.

Smart AFK movement works around that limitation by detecting stalled movement and changing direction.

---

# 🔄 Automatic Reconnection

If the Minecraft connection ends unexpectedly, MC Logger automatically attempts to reconnect.

The reconnect system waits several seconds before creating a new Minecraft connection.

This helps recover from:

* Temporary network problems
* Minecraft server restarts
* Aternos server shutdowns/startups
* Connection resets
* Other temporary connection failures

The AFK system is also cleaned up when the Minecraft connection ends to prevent multiple movement controllers from running simultaneously.

---

# 🔐 LoginSecurity

If the Minecraft server uses **LoginSecurity**, MC Logger automatically sends the configured login command after connecting.

The password is loaded from:

```env
MC_PASSWORD=YOUR_MINECRAFT_LOGIN_PASSWORD
```

The password is never intended to be stored directly in `index.js`.

---

# 🎮 Discord Commands

MC Logger currently provides slash commands for basic bot interaction and status information.

| Command   | Description                                 |
| --------- | ------------------------------------------- |
| `/ping`   | Check whether the Discord bot is responding |
| `/status` | Check Minecraft bot connection status       |
| `/help`   | Display available MC Logger commands        |

Commands are registered for the Discord server configured by the bot.

---

# 📁 Project Structure

The project is intentionally lightweight.

```text
MCLogger/
├── index.js
├── package.json
├── package-lock.json
├── .gitignore
├── .env
└── README.md
```

### Main files

**`index.js`**

Contains the Discord bot, Minecraft connection, chat bridge, commands, reconnect handling, LoginSecurity authentication, and Smart AFK movement.

**`package.json`**

Defines the project metadata and dependencies.

**`.env`**

Contains private configuration such as tokens, channel IDs, and passwords.

**`README.md`**

Project documentation.

---

# ▶️ Running Locally

Install dependencies:

```bash
npm install
```

Then start the bot:

```bash
node index.js
```

You should see the bot initialize and attempt to connect to Discord and Minecraft.

Typical successful Minecraft startup messages include:

```text
🟢 Minecraft login successful!
🟢 MC Logger spawned in Minecraft!
🔐 Logging into LoginSecurity...
🕒 Smart AFK movement system started.
```

---

# ☁️ Hosting

MC Logger can run on Node.js hosting services that support:

* Node.js 22+
* `npm install`
* Persistent Node.js processes
* Environment variables
* Outbound Discord connections
* Outbound Minecraft connections

When using a hosting panel, make sure the project installs the dependencies from `package.json`.

Do not upload or expose your `.env` file publicly.

---

# 🐛 Troubleshooting

## Discord does not connect

Check:

* `DISCORD_TOKEN` is correct
* The token has not been reset or revoked
* The bot has been invited to the Discord server
* Required intents are enabled
* The hosting provider allows outbound Discord connections

---

## Minecraft does not connect

Check:

* The Minecraft server is actually online
* Hostname and port are correct
* The server is running Java Edition
* The Minecraft version matches the bot's supported version
* The hosting provider allows outbound Minecraft connections

Temporary connection errors such as `ECONNRESET` can occur when a server is offline or restarting.

---

## MC Logger connects but does not log in

Check:

* LoginSecurity is installed and active
* `MC_PASSWORD` is correct
* The server is actually requesting `/login`
* The Minecraft account is registered with the expected password

---

## MC Logger gets stuck against a wall

Smart AFK movement is designed specifically to handle this.

The bot monitors its position and turns when it detects that movement has stopped for several seconds.

If it still gets stuck permanently, check the console for Smart AFK messages and investigate the Minecraft physics/version compatibility.

---

## Bot keeps reconnecting

Check both sides of the connection:

```text
Discord
  ↓
Discord Gateway

Minecraft
  ↓
Minecraft server
```

A reconnect loop does not necessarily mean the bot code is broken. The Minecraft server may be offline, restarting, or rejecting the connection.

---

# 🔒 Security

MC Logger handles sensitive credentials.

**Never commit:**

* Discord bot tokens
* Minecraft passwords
* API keys
* Hosting credentials
* Other private environment variables

Use environment variables instead.

GitHub recommends enabling security features such as secret scanning and push protection for repositories where they are available.

---

# 🚧 Current Status

MC Logger is actively developed.

### Implemented

* [x] Discord bot
* [x] Minecraft bot
* [x] Discord → Minecraft bridge
* [x] Minecraft → Discord bridge
* [x] Player join notifications
* [x] Player leave notifications
* [x] Death notifications
* [x] LoginSecurity authentication
* [x] Automatic reconnection
* [x] Discord slash commands
* [x] Minecraft 26.2 support
* [x] Smart AFK movement
* [x] Stuck detection
* [x] Automatic turning when stuck
* [x] Environment-based secrets

### Possible future improvements

* [ ] More advanced obstacle avoidance
* [ ] Configurable AFK behavior
* [ ] More Minecraft event types
* [ ] Rich Discord embeds
* [ ] Improved status information
* [ ] More server-management commands
* [ ] Better movement/pathfinding
* [ ] Expanded configuration options

---

# 🤝 Contributing

Contributions, bug reports, and suggestions are welcome.

If you find a problem:

1. Check the existing issues.
2. Reproduce the problem if possible.
3. Include relevant console output.
4. Remove all private credentials before posting logs.
5. Open an issue with a clear description.

For code changes, create a branch and submit a pull request.

---

# 📜 License

This project is currently distributed under the license specified in the repository.

See [`LICENSE`](LICENSE) if present.

---

# 👨‍💻 Author

**Pranab Mukherjee**

MC Logger is a personal project built to experiment with:

* Node.js
* Discord bots
* Minecraft automation
* Mineflayer
* Server integrations
* Real-time message bridges

---

## ⭐ Project

If you find MC Logger useful or interesting, consider giving the repository a ⭐ on GitHub.

**Repository:** `Pranab-dev/MCLogger`
