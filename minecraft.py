from __future__ import annotations

import asyncio
import inspect
import json
import logging
import math
import random
import re
import time
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from protobot import MovementInput
from protobot.session import BotSession, SessionConfig
from protobot.text import plain_text

if TYPE_CHECKING:
    from discord_bot import MCLoggerDiscord

log = logging.getLogger("mclogger.minecraft")

MC_TRANSLATIONS: dict[str, str] = {
    # Join / Leave
    "multiplayer.player.joined": "%s joined the game",
    "multiplayer.player.join": "%s joined the game",
    "multiplayer.player.joined.renamed": "%s (formerly known as %s) joined the game",
    "multiplayer.player.left": "%s left the game",
    "multiplayer.player.leave": "%s left the game",
    # Chat & Admin formats
    "chat.type.text": "<%s> %s",
    "chat.type.emote": "* %s %s",
    "chat.type.announcement": "[%s] %s",
    "chat.type.admin": "[%s: %s]",
    "chat.admin": "[%s: %s]",
    "chat.type.team.text": "%s <%s> %s",
    "chat.type.team.sent": "-> %s <%s> %s",
    "commands.message.display.incoming": "%s whispers to you: %s",
    "commands.message.display.outgoing": "You whisper to %s: %s",
    # Advancements & Sleep
    "chat.type.advancement.task": "%s has made the advancement %s",
    "chat.type.advancement.goal": "%s has reached the goal %s",
    "chat.type.advancement.challenge": "%s has completed the challenge %s",
    "sleep.players_sleeping": "%s/%s players sleeping",
    "sleep.skipping_night": "Sleeping through this night",
    # Common Admin Command Outputs
    "commands.gamemode.success.self": "Set own game mode to %s",
    "commands.gamemode.success.other": "Set %s's game mode to %s",
    "gameMode.survival": "Survival Mode",
    "gameMode.creative": "Creative Mode",
    "gameMode.adventure": "Adventure Mode",
    "gameMode.spectator": "Spectator Mode",
    "commands.time.set": "Set the time to %s",
    "commands.weather.set.clear": "Set the weather to clear",
    "commands.weather.set.rain": "Set the weather to rain",
    "commands.weather.set.thunder": "Set the weather to rain & thunder",
    "commands.tp.success.entity.single": "Teleported %s to %s",
    "commands.tp.success.coordinates": "Teleported %s to %s, %s, %s",
    "commands.give.success.single": "Gave %s %s to %s",
    "commands.kill.success.single": "Killed %s",
    "commands.op.success": "Made %s a server operator",
    "commands.deop.success": "Made %s no longer a server operator",
    "commands.kick.success": "Kicked %s: %s",
    "commands.ban.success": "Banned %s: %s",
    "commands.pardon.success": "Unbanned %s",
    "commands.whitelist.add.success": "Added %s to the whitelist",
    "commands.whitelist.remove.success": "Removed %s from the whitelist",
    # Common Death Messages
    "death.attack.mob": "%1$s was slain by %2$s",
    "death.attack.player": "%1$s was slain by %2$s",
    "death.attack.player.item": "%1$s was slain by %2$s using %3$s",
    "death.attack.arrow": "%1$s was shot by %2$s",
    "death.attack.explosion": "%1$s blew up",
    "death.attack.explosion.player": "%1$s was blown up by %2$s",
    "death.attack.fall": "%1$s hit the ground too hard",
    "death.fell.accident.generic": "%1$s fell from a high place",
    "death.attack.Lava": "%1$s tried to swim in lava",
    "death.attack.lava": "%1$s tried to swim in lava",
    "death.attack.inFire": "%1$s went up in flames",
    "death.attack.onFire": "%1$s burned to death",
    "death.attack.drown": "%1$s drowned",
    "death.attack.starve": "%1$s starved to death",
    "death.attack.suffocation": "%1$s suffocated in a wall",
    "death.attack.outOfWorld": "%1$s fell out of the world",
    "death.attack.generic": "%1$s died",
    "death.attack.magic": "%1$s was killed by magic",
}

_lang_path = Path("en_us.json")
if _lang_path.is_file():
    try:
        with _lang_path.open(encoding="utf-8") as _f:
            _loaded = json.load(_f)
            if isinstance(_loaded, dict):
                MC_TRANSLATIONS = {**_loaded, **MC_TRANSLATIONS}
    except Exception:
        log.warning("Could not load en_us.json; using built-in translations.")

_FORMAT_SPEC_RE = re.compile(r"%(?:(\d+)\$)?([s%])")
_MC_COLOR_RE = re.compile(r"§[0-9a-fk-orA-FK-OR]")
_HUMANIZE_PREFIXES = (
    "entity.minecraft.",
    "block.minecraft.",
    "item.minecraft.",
    "biome.minecraft.",
    "effect.minecraft.",
    "enchantment.minecraft.",
)

# Inspect MovementInput once so optional fields (strafe, jump, sneak, sprint)
# are used when supported by the installed protobot version and safely ignored otherwise.
try:
    _MOVEMENT_PARAMS = set(inspect.signature(MovementInput).parameters.keys())
except Exception:
    _MOVEMENT_PARAMS = {"forward"}


def _build_movement_input(
    forward: float = 0.0,
    strafe: float = 0.0,
    jump: bool = False,
    sneak: bool = False,
    sprint: bool = False,
) -> MovementInput:
    kwargs: dict[str, Any] = {}
    if "forward" in _MOVEMENT_PARAMS:
        kwargs["forward"] = forward
    if "strafe" in _MOVEMENT_PARAMS:
        kwargs["strafe"] = strafe
    elif "left" in _MOVEMENT_PARAMS and "right" in _MOVEMENT_PARAMS:
        kwargs["left"] = strafe > 0
        kwargs["right"] = strafe < 0
    if "jump" in _MOVEMENT_PARAMS:
        kwargs["jump"] = jump
    if "sneak" in _MOVEMENT_PARAMS:
        kwargs["sneak"] = sneak
    elif "shift" in _MOVEMENT_PARAMS:
        kwargs["shift"] = sneak
    if "sprint" in _MOVEMENT_PARAMS:
        kwargs["sprint"] = sprint

    try:
        return MovementInput(**kwargs)
    except Exception:
        return MovementInput(forward=forward) if forward else MovementInput()


def _apply_template(template: str, args: list[str]) -> str:
    seq_idx = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal seq_idx
        pos_group, spec = match.groups()
        if spec == "%":
            return "%"
        if pos_group is not None:
            idx = int(pos_group) - 1
        else:
            idx = seq_idx
            seq_idx += 1
        return args[idx] if 0 <= idx < len(args) else match.group(0)

    return _FORMAT_SPEC_RE.sub(_replace, template)


def _format_translation(
    key: str,
    args: list[str],
    fallback: str | None = None,
) -> str:
    template = MC_TRANSLATIONS.get(key) or fallback
    if template:
        return _apply_template(template, args)

    for prefix in _HUMANIZE_PREFIXES:
        if key.startswith(prefix) and not args:
            return key[len(prefix):].replace("_", " ").title()

    if args:
        return f"{' '.join(arg for arg in args if arg)} ({key})"

    return key


def render_chat_component(component: Any) -> str:
    """Recursively convert a Minecraft chat component into readable text."""
    if component is None:
        return ""
    if isinstance(component, str):
        return _MC_COLOR_RE.sub("", component)
    if isinstance(component, (int, float, bool)):
        return str(component)
    if isinstance(component, (list, tuple)):
        return "".join(render_chat_component(item) for item in component)

    if not isinstance(component, Mapping):
        if hasattr(component, "to_dict") and callable(component.to_dict):
            component = component.to_dict()
        elif hasattr(component, "__dict__"):
            component = vars(component)
        else:
            return _MC_COLOR_RE.sub("", plain_text(component))

    base = ""
    translate_key = component.get("translate")
    if translate_key is not None:
        raw_args = (
            component.get("with")
            or component.get("with_")
            or component.get("args")
            or []
        )
        if not isinstance(raw_args, (list, tuple)):
            raw_args = [raw_args]
        rendered_args = [render_chat_component(arg) for arg in raw_args]
        fallback = component.get("fallback")
        base = _format_translation(
            str(translate_key),
            rendered_args,
            str(fallback) if fallback is not None else None,
        )
    elif component.get("text") is not None:
        base = str(component["text"])
    elif component.get("") is not None:
        base = render_chat_component(component[""])

    extra = component.get("extra")
    if isinstance(extra, (list, tuple)):
        base += "".join(render_chat_component(item) for item in extra)

    return _MC_COLOR_RE.sub("", base)


class SmartAFKSession(BotSession):
    """
    Human-like Smart AFK tailored for a 5x3 bedrock enclosure.
    Mixes short walks, strafes, jumps, sneaks, smooth head turns,
    and occasional arm swings / hotbar shifts while turning away from walls.
    """

    async def _maybe_player_gesture(self, bot) -> None:
        """Perform a subtle player gesture (arm swing or hotbar change) if supported."""
        try:
            roll = random.random()
            if roll < 0.65:
                for attr in ("swing_arm", "send_swing_arm", "arm_swing"):
                    fn = getattr(bot, attr, None)
                    if callable(fn):
                        res = fn()
                        if inspect.isawaitable(res):
                            await res
                        break
            else:
                slot = random.randint(0, 8)
                for attr in ("set_held_item", "send_held_item_change", "select_slot"):
                    fn = getattr(bot, attr, None)
                    if callable(fn):
                        res = fn(slot)
                        if inspect.isawaitable(res):
                            await res
                        break
        except Exception:
            pass

    async def _tick_loop(self, bot) -> None:
        log.info("Minecraft human-like Smart AFK tick loop started.")

        now = time.monotonic()
        next_state_change = now
        next_look_change = now
        next_gesture = now + random.uniform(4.0, 11.0)
        last_pos_check = now

        last_pos = (float(bot.player.x), float(bot.player.z))
        stuck_since: float | None = None

        forward = 0.0
        strafe = 0.0
        jump = False
        sneak = False
        sprint = False
        jump_until = 0.0

        target_yaw = float(getattr(bot.player, "yaw", 0.0))
        target_pitch = 0.0

        while not bot.closed.is_set() and not self._stop.is_set():
            now = time.monotonic()
            afk_enabled = bool(getattr(bot, "_mclogger_afk_enabled", False))

            if afk_enabled:
                # 1. Pick a new human-like movement state every few seconds
                if now >= next_state_change:
                    choice = random.random()
                    if choice < 0.25:
                        # Pause and chill like a player reading chat or looking around
                        forward, strafe, sneak, sprint = 0.0, 0.0, False, False
                        next_state_change = now + random.uniform(1.2, 4.0)
                    elif choice < 0.58:
                        # Walk forward with optional slight strafe
                        forward = 1.0
                        strafe = random.choice((0.0, 0.0, -0.5, 0.5))
                        sneak = False
                        sprint = random.random() < 0.25
                        next_state_change = now + random.uniform(1.0, 2.8)
                    elif choice < 0.75:
                        # Step backward or strafe sideways inside the 5x3 box
                        forward = random.choice((-1.0, 0.0))
                        strafe = random.choice((-1.0, 1.0)) if forward == 0.0 else 0.0
                        sneak = False
                        sprint = False
                        next_state_change = now + random.uniform(0.8, 2.0)
                    elif choice < 0.90:
                        # Crouch / sneak briefly like players do in tight spaces
                        forward = random.choice((0.0, 0.5, -0.5))
                        strafe = random.choice((0.0, -0.5, 0.5))
                        sneak = True
                        sprint = False
                        next_state_change = now + random.uniform(0.9, 2.4)
                    else:
                        # Hop while moving
                        forward = random.choice((0.0, 1.0))
                        strafe = random.choice((0.0, -0.5, 0.5))
                        sneak = False
                        sprint = False
                        jump_until = now + random.uniform(0.25, 0.55)
                        next_state_change = now + random.uniform(1.0, 2.2)

                    if random.random() < 0.22:
                        jump_until = max(jump_until, now + random.uniform(0.15, 0.35))

                jump = now < jump_until

                # 2. Pick new head look targets periodically
                if now >= next_look_change:
                    cur_yaw = float(getattr(bot.player, "yaw", 0.0))
                    target_yaw = (cur_yaw + random.uniform(-110.0, 110.0)) % 360.0
                    target_pitch = random.uniform(-28.0, 32.0)
                    next_look_change = now + random.uniform(1.4, 4.8)

                # Smoothly interpolate head rotation toward target_yaw / target_pitch
                try:
                    cur_yaw = float(getattr(bot.player, "yaw", 0.0))
                    cur_pitch = float(getattr(bot.player, "pitch", 0.0))
                    yaw_diff = ((target_yaw - cur_yaw + 180.0) % 360.0) - 180.0
                    pitch_diff = target_pitch - cur_pitch

                    if abs(yaw_diff) > 1.2 or abs(pitch_diff) > 1.2:
                        step_yaw = (
                            cur_yaw
                            + max(-16.0, min(16.0, yaw_diff * 0.32))
                            + random.uniform(-0.4, 0.4)
                        ) % 360.0
                        step_pitch = max(
                            -85.0,
                            min(
                                85.0,
                                cur_pitch
                                + max(-9.0, min(9.0, pitch_diff * 0.32))
                                + random.uniform(-0.25, 0.25),
                            ),
                        )
                        await bot.send_look(step_yaw, step_pitch)
                except Exception:
                    log.debug("Smart AFK look interpolation skipped.", exc_info=True)

                # 3. Occasional arm swing or hotbar check
                if now >= next_gesture:
                    await self._maybe_player_gesture(bot)
                    next_gesture = now + random.uniform(4.5, 14.0)

                # 4. Wall / corner detection inside the 5x3 bedrock prison
                if now - last_pos_check >= 0.35:
                    cur_pos = (float(bot.player.x), float(bot.player.z))
                    dist = math.hypot(
                        cur_pos[0] - last_pos[0],
                        cur_pos[1] - last_pos[1],
                    )
                    trying_to_move = abs(forward) > 0.1 or abs(strafe) > 0.1

                    if trying_to_move and dist < 0.04:
                        if stuck_since is None:
                            stuck_since = now
                        elif now - stuck_since >= 0.65:
                            # Turn away from the bedrock wall and reverse/strafe
                            cur_yaw = float(getattr(bot.player, "yaw", 0.0))
                            turn_offset = random.uniform(115.0, 245.0)
                            target_yaw = (cur_yaw + turn_offset) % 360.0
                            target_pitch = random.uniform(-18.0, 22.0)
                            forward = -forward if forward != 0.0 else 1.0
                            strafe = random.choice((-1.0, 0.0, 1.0))
                            if random.random() < 0.4:
                                jump_until = now + 0.25
                            stuck_since = None
                    else:
                        stuck_since = None

                    last_pos = cur_pos
                    last_pos_check = now

                await bot.tick(
                    _build_movement_input(
                        forward=forward,
                        strafe=strafe,
                        jump=jump,
                        sneak=sneak,
                        sprint=sprint,
                    )
                )
            else:
                await bot.tick(_build_movement_input())

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
        self._outgoing_messages: dict[str, float] = {}
        self._explicit_stop: bool = False
        self._watchdog_task: asyncio.Task | None = None

    def _create_session(self) -> SmartAFKSession:
        async def offline_credentials():
            return self.config.mc_username, None, None

        # Explicitly pinned to the single configured server host & port,
        # with infinite reconnect attempts and SmartAFKSession handling anti-AFK.
        session_config = SessionConfig(
            host=self.config.mc_host,
            port=self.config.mc_port,
            version=self.config.mc_version,
            online_mode=False,
            offline_username=self.config.mc_username,
            reconnect=True,
            reconnect_delay=self.config.reconnect_delay,
            reconnect_max_attempts=None,
            anti_kick=False,
        )

        session = SmartAFKSession(
            session_config,
            credentials=offline_credentials,
        )

        session.events.on(
            "session_connecting",
            self._on_connecting,
        )
        session.events.on(
            "session_ready",
            self._on_session_ready,
        )
        session.events.on(
            "session_disconnected",
            self._on_disconnected,
        )
        session.events.on(
            "session_stop",
            self._on_session_stop,
        )
        return session

    async def start(self) -> None:
        self._explicit_stop = False
        self.session = self._create_session()
        self.session.start_background()
        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(
                self._ensure_forever_loop()
            )
        log.info(
            "Minecraft reconnect manager started (pinned to %s:%s).",
            self.config.mc_host,
            self.config.mc_port,
        )

    async def _ensure_forever_loop(self) -> None:
        """
        Watchdog that guarantees the bot never stops trying to connect to the
        configured server unless stop() was explicitly called during shutdown.
        """
        while not self._explicit_stop:
            await asyncio.sleep(max(5.0, float(self.config.reconnect_delay)))
            if self._explicit_stop:
                break
            if self.session is None or not self.session.running:
                log.warning(
                    "Minecraft session stopped unexpectedly; restarting reconnect loop for %s:%s.",
                    self.config.mc_host,
                    self.config.mc_port,
                )
                try:
                    self.session = self._create_session()
                    self.session.start_background()
                except Exception:
                    log.exception("Failed to restart Minecraft session; retrying.")

    async def stop(self) -> None:
        self._explicit_stop = True
        if self._watchdog_task is not None and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        if self.session is not None:
            self.session.request_stop()

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

        bot.on("player_chat", self._on_player_chat)
        bot.on("system_chat", self._on_system_chat)

        bot.on("world_ready", lambda world: self._schedule_login(bot))

        bot.on("error", self._on_bot_error)
        bot.on("close", self._on_bot_close)

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

    async def _on_player_chat(
        self,
        sender,
        name,
        message,
        chat_type_id,
        target_name,
    ) -> None:
        """Forward incoming player chat to the normal Minecraft channel."""

        player_name = render_chat_component(name).strip() or "Unknown"
        text = render_chat_component(message).strip()

        if not text:
            return

        if player_name.casefold() == self.config.mc_username.casefold():
            return

        self._prune_outgoing()

        if text in self._outgoing_messages:
            self._outgoing_messages.pop(text, None)
            return

        if target_name is not None:
            target = render_chat_component(target_name).strip()
            if target:
                await self.discord.send_minecraft_chat(
                    f"**{player_name} -> {target}:** {text}"
                )
                return

        await self.discord.send_minecraft_chat(
            f"**{player_name}:** {text}"
        )

    async def _on_system_chat(
        self,
        component,
        overlay,
    ) -> None:
        """Forward server-sent chat components."""

        if overlay:
            return

        text = render_chat_component(component).strip()

        if not text:
            return

        self._prune_outgoing()
        if any(msg in text for msg in self._outgoing_messages):
            return

        await self.discord.send_minecraft_chat(text)

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

        if not self._explicit_stop:
            await self.discord.log_to_discord(
                "⚠️ Minecraft session stopped unexpectedly; watchdog will restart reconnect loop."
            )
        else:
            await self.discord.log_to_discord(
                "⏹️ Minecraft reconnect session stopped."
            )

    def status_text(self) -> str:
        if self.session is None:
            return "Not started"

        bot = self.session.bot

        if bot is not None and not bot.closed.is_set():
            return (
                f"Connected as **{bot.username}** "
                "(offline-mode)"
            )

        if self.session.running or not self._explicit_stop:
            return "Connecting / waiting to reconnect"

        return "Offline"
