# MC Logger

**MC Logger** is a Node.js Discord bot that bridges a Minecraft server with Discord.

It connects to a Minecraft server using [Mineflayer](https://github.com/PrismarineJS/mineflayer) and connects to Discord using [discord.js](https://discord.js.org/), allowing Minecraft activity to be shared with a designated Discord channel and Discord messages to be sent back into Minecraft.

## Features

* **Minecraft → Discord bridge**

  * Minecraft messages are forwarded to the configured Discord channel.
  * Player join events are announced in Discord.
  * Player leave events are announced in Discord.
* **Discord → Minecraft bridge**

  * Messages sent in the configured Discord channel are sent into Minecraft.
  * Messages are prefixed with the Discord user's name.
* **Automatic reconnection**

  * MC Logger periodically attempts to reconnect when the Minecraft connection ends.
* **Discord slash commands**

  * `/ping`
  * `/status`
  * `/help`
  * `/about`
* **Minecraft authentication**

  * Supports automatic LoginSecurity login through an environment variable.
* **Environment-based configuration**

  * Sensitive credentials are stored outside the source code in `.env`.

## How It Works

```text
                  ┌──────────────────────┐
                  │   Minecraft Server   │
                  └──────────┬───────────┘
                             │
                         Mineflayer
                             │
                             ▼
                  ┌──────────────────────┐
                  │      MC Logger       │
                  │       Node.js        │
                  └──────────┬───────────┘
                             │
                         discord.js
                             │
                             ▼
                  ┌──────────────────────┐
                  │       Discord        │
                  │       Server         │
                  └──────────────────────┘
```

### Minecraft → Discord

Minecraft messages received by MC Logger are forwarded to the configured Discord channel.

Player activity is also reported:

```text
🟢 Player joined the game
🔴 Player left the game
```

### Discord → Minecraft

Messages sent in the configured Minecraft Discord channel are forwarded to Minecraft in the following format:

```text
[Discord] username: message
```

Messages sent by bots are ignored to prevent unnecessary message loops.

## Discord Commands

| Command   | Description                              |
| --------- | ---------------------------------------- |
| `/ping`   | Check whether MC Logger is responding    |
| `/status` | Check the Minecraft connection status    |
| `/help`   | Display the available MC Logger commands |
| `/about`   | Information about the bot |

## Requirements

* **Node.js**
* A Discord application/bot
* A Discord server where the bot can operate
* A Minecraft server accessible to the Mineflayer client
* A Minecraft account/bot account accepted by the server
* The required Discord bot permissions and intents

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Pranab-dev/MCLogger.git
cd MCLogger
```

### 2. Install dependencies

```bash
npm install
```

The project currently uses:

* `discord.js`
* `dotenv`
* `mineflayer`

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
DISCORD_TOKEN=your_discord_bot_token
CLIENT_ID=your_discord_application_id
GUILD_ID=your_discord_server_id
MC_PASSWORD=your_minecraft_password
MINECRAFT_CHANNEL_ID=your_discord_channel_id
```

**Never commit your `.env` file.**

The repository already includes `.env` in `.gitignore`.

### 4. Register slash commands

Run:

```bash
node deploy-commands.js
```

### 5. Start MC Logger

Run:

```bash
node index.js
```

If everything is configured correctly, the Discord bot will log in and MC Logger will begin attempting to connect to Minecraft.

## Configuration

The Minecraft server connection is currently configured in `index.js`.

The project currently uses:

```text
Host: thenexus.aternos.me
Port: 32552
Minecraft username: MCLogger
```

The Minecraft password is loaded from:

```env
MC_PASSWORD=your_minecraft_password
```

The Discord channel used for the bridge is loaded from:

```env
MINECRAFT_CHANNEL_ID=your_discord_channel_id
```

The Discord bot token is loaded from:

```env
DISCORD_TOKEN=your_discord_bot_token
```

## Project Structure

```text
MCLogger/
│
├── commands/
│   ├── help.js
│   ├── ping.js
│   └── status.js
│
├── deploy-commands.js
├── index.js
├── mc-test.js
├── package.json
├── package-lock.json
├── .gitignore
└── README.md
```

### Main files

**`index.js`**

The main application. Handles:

* Discord client initialization
* Minecraft connection
* Minecraft → Discord messages
* Discord → Minecraft messages
* Player join/leave events
* Reconnection
* Slash-command handling

**`deploy-commands.js`**

Registers the Discord slash commands.

**`mc-test.js`**

A standalone Mineflayer connection/testing script.

**`commands/`**

Contains the Discord slash command implementations.

## Reconnection

When the Minecraft connection ends, MC Logger clears the connection state and attempts to reconnect.

The current reconnect interval is **5 seconds**.

```text
Minecraft online
       │
       ▼
   Connected
       │
       │ connection lost
       ▼
   Disconnected
       │
       │ wait 5 seconds
       ▼
   Try again
       │
       └──────► repeat
```

This allows MC Logger to work with Minecraft servers that are not continuously online.

## Security

MC Logger uses environment variables for sensitive configuration.

Do **not** put the following directly into committed source code:

* Discord bot tokens
* Minecraft passwords
* Other private credentials

The `.gitignore` file excludes:

```text
.env
node_modules/
```

If a credential is ever accidentally exposed, revoke or change it immediately.

## Development

After modifying the project:

```bash
git add .
git commit -m "Describe your changes"
git push
```

Install dependencies again after cloning:

```bash
npm install
```

## Project Status

**Active development**

MC Logger is currently a working Discord ↔ Minecraft bridge project.

The current implementation focuses on:

* Discord integration
* Minecraft connectivity
* Message synchronization
* Player join/leave notifications
* Automatic reconnection
* Basic Discord commands

Additional monitoring and server-status functionality can be added as the project develops.

## Author

**Pranab Mukherjee**

MC Logger is an independent personal project built for Minecraft and Discord integration.

## License

This project is licensed under the **MIT License**.

See [`LICENSE`](LICENSE) for the full license text.
