# MC Logger — Python rewrite

Python Discord ↔ Minecraft bridge using `discord.py` and ProtoBot 1.2.7.

## Included

- Discord slash commands: `/ping`, `/status`, `/help`
- Discord chat channel → Minecraft chat (200-character input cap)
- Minecraft player chat → Discord
- Minecraft system chat and action-bar messages → Discord event-log channel
- Player join/leave and death logs → Discord event-log channel
- Connection, protocol error, disconnect, and reconnect logs → Discord event-log channel
- Persistent local logs in `logs/mclogger.log`, rotated daily with 30 days of history
- Discord-originated Minecraft messages are also recorded locally
- Offline-mode Minecraft login as `MCLogger`
- Sends `/login MC_PASSWORD` after the first world chunk
- Waits 2 seconds after sending the login command, then enables Smart AFK
- Smart AFK alternates forward/back every 4 minutes; checks movement every second and turns 90° after being stuck for 3 seconds
- Discord remains independent of the Minecraft reconnect loop
- Minecraft reconnect delay: 30 seconds

## Setup (Windows CMD)

1. Extract the ZIP.
2. Open CMD in the extracted `MCLogger_Python` folder.
3. Create your environment file:

   ```cmd
   copy .env.example .env
   ```

4. Edit `.env` and fill in:
   - `DISCORD_TOKEN`
   - `MINECRAFT_CHANNEL_ID`
   - `BOT_LOG_CHANNEL_ID`
   - `MC_PASSWORD`

   Keep `.env` private. Never send the token or password to anyone.

5. Install dependencies:

   ```cmd
   python -m pip install -r requirements.txt
   ```

6. Start MC Logger:

   ```cmd
   python main.py
   ```

## Discord setup

In the Discord Developer Portal, enable the **Message Content Intent** for the bot.
Invite it with the `bot` and `applications.commands` scopes. It needs permission to:
- View channels
- Send messages
- Read message history
- Use application commands

The bot needs access to both configured channels. `MINECRAFT_CHANNEL_ID` is where player chat is bridged. `BOT_LOG_CHANNEL_ID` receives system messages, action-bar messages, join/leave/death events, and connection events. Local logs are written under `logs/` beside `main.py`.

## Minecraft configuration

Defaults:
- Host: `nexusforever.aternos.me`
- Port: `15629`
- Version: `26.3`
- Username: `MCLogger`
- Login mode: offline/cracked
- Reconnect delay: 30 seconds

The server must permit offline-mode connections and the EasyAuth `/login` command. ProtoBot's `world_ready` event is emitted when the first world chunk is loaded.

## Logging coverage

The logger records every message/event exposed through the ProtoBot event API currently used by this project: `player_chat`, `system_chat`, `player_join`, `player_leave`, and `death`, plus connection/session events. Some server activity is not delivered to a client as chat (for example, private plugin internals or commands typed by other players); those cannot be guaranteed by a client-side bot. Action-bar/system overlays are included and may be frequent on some servers.

## Notes

- The old Node.js project is not modified by this rewrite.
- The password and Discord token belong only in `.env`.
- If the server's chat policy or plugin changes, check the console and Discord log channel for the exact error.
- Smart AFK uses ProtoBot's physics tick loop rather than launching a second competing movement loop.
