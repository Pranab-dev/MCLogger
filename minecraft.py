from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import TYPE_CHECKING

from protobot import MovementInput
from protobot.session import BotSession, SessionConfig
from protobot.text import plain_text

if TYPE_CHECKING:
    from discord_bot import MCLoggerDiscord

log = logging.getLogger("mclogger.minecraft")


class SmartAFKSession(BotSession):
    """BotSession with the project's periodic forward/back Smart AFK pattern."""

    async def _tick_loop(self, bot) -> None:
        log.info("Minecraft tick loop started.")

        direction = 1.0
        direction_started = time.monotonic()
        last_position_check = time.monotonic()
        last_position = (bot.player.x, bot.player.z)
        stuck_since: float | None = None

        while not bot.closed.is_set() and not self._stop.is_set():
            now = time.monotonic()
            afk_enabled = bool(
                getattr(bot, "_mclogger_afk_enabled", False)
            )

            if afk_enabled:
                # Alternate forward/backward every four minutes.
                if now - direction_started >= 240:
                    direction *= -1.0
                    direction_started = now
                    log.info("Smart AFK changed walking direction.")

                await bot.tick(MovementInput(forward=direction))

                # Check movement once per second.
                if now - last_position_check >= 1.0:
                    current_position = (bot.player.x, bot.player.z)

                    distance = math.hypot(
                        current_position[0] - last_position[0],
                        current_position[1] - last_position[1],
                    )

                    if distance < 0.08:
                        if stuck_since is None:
                            stuck_since = now
                        elif now - stuck_since >= 3.0:
                            try:
                                yaw = float(bot.player.yaw)
                                pitch = float(bot.player.pitch)

                                await bot.send_look(
                                    (yaw + 90.0) % 360.0,
                                    pitch,
                                )
                            except Exception:
                                log.exception(
                                    "Smart AFK could not rotate the bot."
                                )

                            stuck_since = None
                    else:
                        stuck_since = None

                    last_position = current_position
                    last_position_check = now
            else:
                await bot.tick(MovementInput())

            await asyncio.sleep(self._tick_interval)

        if self._stop.is_set():
            log.info("Minecraft session is stopping.")


class MinecraftController:
    """Manages the Minecraft connection and Discord chat bridge."""

    def __init__(
        self,
        discord_client: "MCLoggerDiscord",
        config,
    ):
        self.discord = discord_client
        self.config = config

        self.session: SmartAFKSession | None = None
        self._login_started: set[int] = set()

        # Messages sent from Discord are remembered briefly so their
        # Minecraft echo is not sent straight back to Discord.
        self._outgoing_messages: dict[str, float] = {}

    async def start(self) -> None:
        async def offline_credentials():
            # Offline-mode server. EasyAuth is handled in-game.
            return self.config.mc_username, None, None

        session_config = SessionConfig(
            host=self.config.mc_host,
            port=self.config.mc_port,
            version=self.config.mc_version,
            online_mode=False,
            offline_username=self.config.mc_username,
            reconnect=True,
            reconnect_delay=self.config.reconnect_delay,
            reconnect_max_attempts=None,
            anti_kick=True,
        )

        self.session = SmartAFKSession(
            session_config,
            credentials=offline_credentials,
        )

        self.session.events.on(
            "session_connecting",
            self._on_connecting,
        )
        self.session.events.on(
            "session_ready",
            self._on_session_ready,
        )
        self.session.events.on(
            "session_disconnected",
            self._on_disconnected,
        )
        self.session.events.on(
            "session_stop",
            self._on_session_stop,
        )

        self.session.start_background()
        log.info("Minecraft reconnect manager started.")

    async def stop(self) -> None:
        if self.session is not None:
            self.session.request_stop()

    # ---------------------------------------------------------
    # Connection lifecycle
    # ---------------------------------------------------------

    async def _on_connecting(self, attempt: int) -> None:
        message = (
            f"Connection attempt #{attempt} to "
            f"{self.config.mc_host}:{self.config.mc_port}."
        )

        log.info(message)

        await self.discord.log_to_discord(
            f"🔄 {message}"
        )

    async def _on_session_ready(self, bot) -> None:
        log.info("Minecraft connected as %s.", bot.username)

        await self.discord.log_to_discord(
            f"🟢 Minecraft connected as **{bot.username}**."
        )

        # Register chat handlers on each newly created Bot instance.
        # ProtoBot creates a fresh Bot after a reconnect.
        bot.on("player_chat", self._on_player_chat)
        bot.on("system_chat", self._on_system_chat)

        bot.on("world_ready", lambda world: self._schedule_login(bot))

        bot.on("error", self._on_bot_error)
        bot.on("close", self._on_bot_close)

        # The world may already be ready by the time this handler runs.
        world_event = getattr(bot, "world_ready", None)

        if world_event is not None and world_event.is_set():
            self._schedule_login(bot)

    def _schedule_login(self, bot) -> None:
        identity = id(bot)

        if identity in self._login_started:
            return

        self._login_started.add(identity)

        asyncio.create_task(
            self._login_then_enable_afk(bot)
        )

    async def _login_then_enable_afk(self, bot) -> None:
        if bot.closed.is_set():
            return

        try:
            command = f"/login {self.config.mc_password}"

            await bot.send_command(command)

            log.info("Sent EasyAuth login command.")

            await asyncio.sleep(2.0)

            if not bot.closed.is_set():
                bot._mclogger_afk_enabled = True

                log.info("Smart AFK enabled.")

                await self.discord.log_to_discord(
                    "🔐 Minecraft login command sent; Smart AFK enabled."
                )

        except Exception:
            log.exception(
                "Minecraft login / Smart AFK startup failed."
            )

            await self.discord.log_to_discord(
                "⚠️ Minecraft login or Smart AFK startup failed. "
                "Check the terminal."
            )

    # ---------------------------------------------------------
    # Minecraft -> Discord chat forwarding
    # ---------------------------------------------------------

    async def _on_player_chat(
        self,
        sender,
        name,
        message,
        chat_type_id,
        target_name,
    ) -> None:
        """Forward incoming player chat to the normal Minecraft channel."""

        player_name = plain_text(name).strip() or "Unknown"
        text = plain_text(message).strip()

        if not text:
            return

        # Do not relay MCLogger's own messages back to Discord.
        if player_name.casefold() == self.config.mc_username.casefold():
            return

        self._prune_outgoing()

        # Also suppress echoes of messages sent from Discord.
        if text in self._outgoing_messages:
            self._outgoing_messages.pop(text, None)
            return

        await self.discord.send_minecraft_chat(
            f"**{player_name}:** {text}"
        )

    async def _on_system_chat(
        self,
        component,
        overlay,
    ) -> None:
        """
        Forward server-sent chat components.

        overlay=True means an action-bar message, not a normal
        chat-window message, so it is intentionally excluded.
        """

        if overlay:
            return

        text = plain_text(component).strip()

        if not text:
            return

        await self.discord.send_minecraft_chat(text)

    # ---------------------------------------------------------
    # Discord -> Minecraft chat forwarding
    # ---------------------------------------------------------

    async def send_discord_chat(
        self,
        author: str,
        content: str,
    ) -> bool:
        session = self.session
        bot = session.bot if session is not None else None

        if bot is None or bot.closed.is_set():
            return False

        outgoing = f"[Discord] {author}: {content}"

        # Keep the message within Minecraft's chat length limit.
        outgoing = outgoing[:256]

        try:
            await bot.send_message(outgoing)

            self._outgoing_messages[outgoing] = time.monotonic()
            self._prune_outgoing()

            return True

        except Exception:
            log.exception(
                "Could not relay Discord message to Minecraft."
            )
            return False

    def _prune_outgoing(self) -> None:
        cutoff = time.monotonic() - 10.0

        self._outgoing_messages = {
            message: sent_at
            for message, sent_at in self._outgoing_messages.items()
            if sent_at >= cutoff
        }

    # ---------------------------------------------------------
    # Diagnostics: these go to the bot-log channel, NOT chat.
    # ---------------------------------------------------------

    async def _on_bot_error(self, error) -> None:
        log.error("Minecraft protocol error: %s", error)

        await self.discord.log_to_discord(
            f"⚠️ Minecraft error: `{str(error)[:800]}`"
        )

    async def _on_bot_close(self, reason) -> None:
        log.warning(
            "Minecraft connection closed: %s",
            reason,
        )

    async def _on_disconnected(
        self,
        reason,
        attempt: int,
    ) -> None:
        self._login_started.clear()

        reason_text = str(reason or "connection closed")

        log.warning(
            "Minecraft disconnected: %s",
            reason_text,
        )

        await self.discord.log_to_discord(
            f"🔴 Minecraft disconnected (attempt **#{attempt}**): "
            f"`{reason_text[:700]}`. "
            f"Retrying in {self.config.reconnect_delay:g}s."
        )

    async def _on_session_stop(self) -> None:
        log.info("Minecraft reconnect session stopped.")

        await self.discord.log_to_discord(
            "⏹️ Minecraft reconnect session stopped."
        )

    # ---------------------------------------------------------
    # Status
    # ---------------------------------------------------------

    def status_text(self) -> str:
        if self.session is None:
            return "Not started"

        bot = self.session.bot

        if bot is not None and not bot.closed.is_set():
            return (
                f"Connected as **{bot.username}** "
                "(offline-mode)"
            )

        if self.session.running:
            return "Connecting / waiting to reconnect"

        return "Offline"