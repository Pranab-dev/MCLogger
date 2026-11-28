# MCLogger

24/7 Discord ↔ Minecraft bridge, vanilla-emulated Smart AFK companion, and Aternos server manager built with `discord.py`, `ProtoBot`, and pure-Python dependencies for Python 3.13+.

- **Developer:** `@thepixelriftx`
- **Repository:** https://github.com/Pranab-dev/MCLogger

---

## Features

### Discord Integration & Slash Commands
- **Permanent Bot Presence:** Keeps Discord status locked to **Playing Nexus SMP!** across startups and Gateway resumes.
- **Slash Commands:**
  - `/ping` — Check Discord bot latency and responsiveness.
  - `/status` — View Discord connection state, Minecraft bot status, live Aternos server state, and `MCLogger` ban status.
  - `/start` — Send a start signal to the Aternos server using a persisted session cookie.
  - `/unban` — Check Aternos's banned-players list (works whether the server is online or offline) and unban **only** `MCLogger`.
  - `/restart` — Restart the MCLogger backend in-place (via Silly Development / Pterodactyl Panel API if configured, or `os.execv` process re-execution without stopping the container).
  - `/about` — Display project details, developer credit, and repository link.
  - `/help` — Show all available commands and usage instructions.
- **Interaction Timeout Safety:** Automatic fallback to channel replies if container CPU load delays a slash command response past Discord's 3-second window.

### Two-Way Chat & Event Bridge
- **Discord → Minecraft:** Relays messages from `MINECRAFT_CHANNEL_ID` in-game as `[Discord] DisplayName: message` (200-character input cap) and reacts with `⚠️` if delivery fails.
- **Minecraft → Discord:** Relays player chat, whispers, system announcements, join/leave messages, advancements, and death messages to `MINECRAFT_CHANNEL_ID`.
- **Full Translation Resolution:** Automatically downloads official Minecraft `en_us.json` (8,700+ keys) on first boot with a built-in fallback dictionary for join/leave, death, and command messages.
- **Operational & Audit Logging:** Sends connection attempts, disconnects, random-world guard alerts, and slash command audit logs to `BOT_LOG_CHANNEL_ID`, and writes daily rotated local logs to `logs/mclogger.log` (30-day retention).

### Vanilla Client Emulation & Smart AFK
- **Protocol Emulation (Minecraft 26.3):**
  - Emits `minecraft:client_tick_end` at the end of every 50 ms physics tick.
  - Sends `minecraft:brand` (`vanilla`), `client_information` (locale `en_US`, view distance, full skin layers `0x7F`), and `minecraft:player_loaded` once chunks finish loading.
  - Quantizes all yaw/pitch movements to exact vanilla mouse sensitivity GCD steps and adds 1–3 ms natural tick jitter.
- **Human-Like Smart AFK:** Tailored for compact enclosures (such as a 5×3 bedrock box)—blends idle pauses, short walks, strafes, sneaks, jumps, smooth head turns, arm swings, hotbar slot switches, and automatic wall-stuck turnarounds.
- **EasyAuth Login:** Waits for `world_ready`, verifies server identity, sends `/login <MC_PASSWORD>` after a short natural delay, and enables Smart AFK 2 seconds later.

### Reliability & Guards
- **Random-World Guard:** Verifies via Aternos that `nexusforever.aternos.me` is genuinely online before sending `/login` or accepting a connection (and re-checks every 60 seconds), immediately disconnecting if a stranger's server occupies the shared Aternos port.
- **Continuous Reconnect Loop:** Retries every 30 seconds in 400-attempt cycles (`MC_RECONNECT_MAX_ATTEMPTS`) with automatic cycle resets and a DNS/network outage retry loop in `main.py` so temporary host network drops never crash the container.

---

## Project Structure

| File | Purpose |
| :--- | :--- |
| `main.py` | Entry point, daily log rotation, DNS/network retry loop, and in-place `os.execv` restart handler. |
| `config.py` | Loads and validates `.env` configuration variables. |
| `discord_bot.py` | `discord.py` client, slash commands, chat relay, presence manager, and Pterodactyl restart support. |
| `minecraft.py` | `ProtoBot` session controller, vanilla packet emulator, Smart AFK loop, translation renderer, and random-world guard. |
| `aternos_manager.py` | Pure-Python 3.13 Aternos session client for `/start`, `/unban`, `/status`, and server online verification. |
| `requirements.txt` | Pure-Python package dependencies (no C compiler headers required). |

---

## Setup

### 1. Create `.env`

Create a `.env` file in the root directory beside `main.py`:

```env
# Required Discord & Minecraft settings
DISCORD_TOKEN=your_discord_bot_token
MINECRAFT_CHANNEL_ID=123456789012345678
BOT_LOG_CHANNEL_ID=123456789012345678

MC_HOST=nexusforever.aternos.me
MC_PORT=15629
MC_VERSION=26.3
MC_USERNAME=MCLogger
MC_PASSWORD=your_easyauth_password
MC_RECONNECT_DELAY=30
MC_RECONNECT_MAX_ATTEMPTS=400

# Optional: Aternos browser session cookie for /start, /unban, /status, and Random-World Guard
ATERNOS_SESSION=your_aternos_session_cookie
ATERNOS_TOKEN=

# Optional: Silly Development (Pterodactyl) Panel API for container-level /restart
PANEL_URL=[https://panel.sillydev.co.uk](https://panel.sillydev.co.uk)
PANEL_API_KEY=
PANEL_SERVER_ID=
```

> **Note:** Keep `.env` and `.aternos_session` private. Never commit tokens, cookies, or passwords to GitHub.

### 2. Install Dependencies & Run

All dependencies in `requirements.txt` are pure Python and install cleanly on Python 3.13+ without `gcc`, `libxml2`, or `libxslt`:

```bash
python -m pip install -r requirements.txt
python main.py
```

*(On Silly Development / Pterodactyl containers, upload the files to `/home/container/`, set `main.py` as your startup file, and start the server.)*

---

## Discord Bot Setup

1. Open the **Discord Developer Portal** → select your application → **Bot**:
   - Enable **Message Content Intent** under *Privileged Gateway Intents*.
   - Turn **Public Bot** off if you want to keep your bot instance private.
2. Go to **OAuth2 → URL Generator**:
   - **Scopes:** `bot`, `applications.commands`
   - **Bot Permissions:** `View Channels`, `Send Messages`, `Send Messages in Threads`, `Read Message History`, `Add Reactions`
3. Invite the bot using the generated URL and ensure the `MCLogger` role has explicit channel permissions on both `MINECRAFT_CHANNEL_ID` and `BOT_LOG_CHANNEL_ID`.

---

## Obtaining `ATERNOS_SESSION`

1. Log into https://aternos.org/servers/ in a browser with Developer Tools (Desktop Chrome/Edge, or **Mises / Kiwi Browser** on Android).
2. Open **Developer Tools → Application (or Storage) → Cookies → `https://aternos.org`**.
3. Copy the value of **`ATERNOS_SESSION`** and paste it into `.env` without quotes.
4. Close the browser tab without clicking **Log out** inside Aternos (clicking Log out invalidates the session cookie). Note that free Aternos accounts hosted behind datacenter IPs may still encounter Cloudflare `503` challenges on automated AJAX requests; when that happens, start or unban directly in your browser and MCLogger will connect automatically.
