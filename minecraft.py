from __future__ import annotations

import asyncio
import inspect
import json
import logging
import math
import os
import random
import re
import struct
import time
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from protobot import MovementInput
from protobot.session import BotSession, SessionConfig
from protobot.text import plain_text

if TYPE_CHECKING:
    from discord_bot import MCLoggerDiscord

log = logging.getLogger("mclogger.minecraft")

_LANG_URLS = (
    "https://raw.githubusercontent.com/misode/mcmeta/assets-json/assets/minecraft/lang/en_us.json",
    "https://raw.githubusercontent.com/InventivetalentDev/minecraft-assets/1.21.4/assets/minecraft/lang/en_us.json",
)

MC_TRANSLATIONS: dict[str, str] = {
    # --- Multiplayer Join / Leave & Status ---
    "multiplayer.player.joined": "%s joined the game",
    "multiplayer.player.join": "%s joined the game",
    "multiplayer.player.joined.renamed": "%s (formerly known as %s) joined the game",
    "multiplayer.player.left": "%s left the game",
    "multiplayer.player.leave": "%s left the game",
    "multiplayer.downloadingTerrain": "Downloading terrain...",
    "multiplayer.downloadingStats": "Downloading statistics...",
    "multiplayer.stopSleeping": "Leave Bed",
    # --- Multiplayer Disconnect & Kick Reasons ---
    "multiplayer.disconnect.generic": "Disconnected",
    "multiplayer.disconnect.kicked": "Kicked by an operator",
    "multiplayer.disconnect.banned": "You are banned from this server",
    "multiplayer.disconnect.banned.reason": "You are banned from this server.\nReason: %s",
    "multiplayer.disconnect.banned.expiration": "\nYour ban will be removed on %s",
    "multiplayer.disconnect.banned_ip.reason": "Your IP address is banned from this server.\nReason: %s",
    "multiplayer.disconnect.banned_ip.expiration": "\nYour ban will be removed on %s",
    "multiplayer.disconnect.ip_banned": "You have been IP banned from this server",
    "multiplayer.disconnect.not_whitelisted": "You are not white-listed on this server!",
    "multiplayer.disconnect.server_shutdown": "Server closed",
    "multiplayer.disconnect.server_full": "The server is full!",
    "multiplayer.disconnect.outdated_client": "Outdated client! Please use %s",
    "multiplayer.disconnect.outdated_server": "Outdated server! I'm still on %s",
    "multiplayer.disconnect.Incompatible": "Incompatible version: %s",
    "multiplayer.disconnect.flying": "Flying is not enabled on this server",
    "multiplayer.disconnect.idling": "You have been idle for too long!",
    "multiplayer.disconnect.duplicate_login": "You logged in from another location",
    "multiplayer.disconnect.name_taken": "That name is already taken",
    "multiplayer.disconnect.slow_login": "Took too long to log in",
    "multiplayer.disconnect.unverified_username": "Failed to verify username!",
    "multiplayer.disconnect.chat_validation_failed": "Chat message validation failure",
    "multiplayer.disconnect.unsigned_chat": "Received unsigned chat packet",
    "multiplayer.disconnect.illegal_characters": "Illegal characters in chat",
    "multiplayer.disconnect.too_many_pending_chats": "Too many pending chat messages",
    "multiplayer.disconnect.expired_public_key": "Expired profile public key",
    "multiplayer.disconnect.invalid_public_key_signature": "Invalid signature for profile public key",
    "multiplayer.disconnect.invalid_player_data": "Invalid player data",
    "multiplayer.disconnect.invalid_packet": "Server sent an invalid packet",
    "multiplayer.disconnect.unexpected_query_response": "Unexpected custom data from client",
    "multiplayer.disconnect.transfers_disabled": "Server does not accept transfers",
    "disconnect.genericReason": "%s",
    "disconnect.disconnected": "Disconnected by Server",
    "disconnect.lost": "Connection Lost",
    "disconnect.kicked": "Was kicked from the game",
    "disconnect.timeout": "Timed out",
    "disconnect.quitting": "Quitting",
    "disconnect.endOfStream": "End of stream",
    "disconnect.overflow": "Buffer overflow",
    "disconnect.spam": "Kicked for spamming",
    "disconnect.exceeded_packet_rate": "Kicked for exceeding packet rate limit",
    "disconnect.loginFailed": "Failed to login",
    "disconnect.loginFailedInfo": "Failed to login: %s",
    "disconnect.loginFailedInfo.invalidSession": "Invalid session (Try restarting your game and the launcher)",
    "disconnect.loginFailedInfo.serversUnavailable": "The authentication servers are currently not reachable",
    # --- Chat & Team Formats ---
    "chat.type.text": "<%s> %s",
    "chat.type.text.narrate": "%s says %s",
    "chat.type.emote": "* %s %s",
    "chat.type.announcement": "[%s] %s",
    "chat.type.admin": "[%s: %s]",
    "chat.admin": "[%s: %s]",
    "chat.type.team.text": "%s <%s> %s",
    "chat.type.team.sent": "-> %s <%s> %s",
    "chat.type.team.hover": "MessageTeam",
    "chat.type.advancement.task": "%s has made the advancement %s",
    "chat.type.advancement.goal": "%s has reached the goal %s",
    "chat.type.advancement.challenge": "%s has completed the challenge %s",
    "chat.type.achievement": "%s has just earned the achievement %s",
    "chat.type.achievement.taken": "%s has lost the achievement %s",
    "chat.square_brackets": "[%s]",
    "chat.cannotSend": "Cannot send chat message",
    # --- Sleep & Night ---
    "sleep.players_sleeping": "%s/%s players sleeping",
    "sleep.skipping_night": "Sleeping through this night",
    "sleep.not_possible": "You may not rest now",
    "block.minecraft.bed.no_sleep": "You can sleep only at night or during thunderstorms",
    "block.minecraft.bed.not_safe": "You may not rest now; there are monsters nearby",
    "block.minecraft.bed.obstructed": "This bed is obstructed",
    "block.minecraft.bed.occupied": "This bed is occupied",
    "block.minecraft.bed.too_far_away": "You may not rest now; the bed is too far away",
    "block.minecraft.set_spawn": "Respawn point set",
    # --- Game Modes & Difficulties ---
    "gameMode.survival": "Survival Mode",
    "gameMode.creative": "Creative Mode",
    "gameMode.adventure": "Adventure Mode",
    "gameMode.spectator": "Spectator Mode",
    "gameMode.hardcore": "Hardcore Mode!",
    "gameMode.changed": "Your game mode has been updated to %s",
    "options.difficulty.peaceful": "Peaceful",
    "options.difficulty.easy": "Easy",
    "options.difficulty.normal": "Normal",
    "options.difficulty.hard": "Hard",
    "options.difficulty.hardcore": "Hardcore",
    # --- Fall Death Messages (death.fell.*) ---
    "death.fell.accident.generic": "%1$s fell from a high place",
    "death.fell.accident.ladder": "%1$s fell off a ladder",
    "death.fell.accident.vines": "%1$s fell off some vines",
    "death.fell.accident.weeping_vines": "%1$s fell off some weeping vines",
    "death.fell.accident.twisting_vines": "%1$s fell off some twisting vines",
    "death.fell.accident.scaffolding": "%1$s fell off scaffolding",
    "death.fell.accident.other_climbable": "%1$s fell while climbing",
    "death.fell.accident.water": "%1$s fell out of the water",
    "death.fell.killer": "%1$s was doomed to fall",
    "death.fell.assist": "%1$s was doomed to fall by %2$s",
    "death.fell.assist.item": "%1$s was doomed to fall by %2$s using %3$s",
    "death.fell.finish": "%1$s fell too far and was finished by %2$s",
    "death.fell.finish.item": "%1$s fell too far and was finished by %2$s using %3$s",
    # --- Combat & Environmental Death Messages (death.attack.*) ---
    "death.attack.mob": "%1$s was slain by %2$s",
    "death.attack.mob.item": "%1$s was slain by %2$s using %3$s",
    "death.attack.player": "%1$s was slain by %2$s",
    "death.attack.player.item": "%1$s was slain by %2$s using %3$s",
    "death.attack.arrow": "%1$s was shot by %2$s",
    "death.attack.arrow.item": "%1$s was shot by %2$s using %3$s",
    "death.attack.fireball": "%1$s was fireballed by %2$s",
    "death.attack.fireball.item": "%1$s was fireballed by %2$s using %3$s",
    "death.attack.thrown": "%1$s was pummeled by %2$s",
    "death.attack.thrown.item": "%1$s was pummeled by %2$s using %3$s",
    "death.attack.trident": "%1$s was impaled by %2$s",
    "death.attack.trident.item": "%1$s was impaled by %2$s with %3$s",
    "death.attack.thorns": "%1$s was killed trying to hurt %2$s",
    "death.attack.thorns.item": "%1$s was killed by %3$s trying to hurt %2$s",
    "death.attack.spit": "%1$s was spitballed by %2$s",
    "death.attack.fangs": "%1$s was snapped by %2$s",
    "death.attack.Fangs": "%1$s was snapped by %2$s",
    "death.attack.explosion": "%1$s blew up",
    "death.attack.explosion.player": "%1$s was blown up by %2$s",
    "death.attack.explosion.player.item": "%1$s was blown up by %2$s using %3$s",
    "death.attack.fall": "%1$s hit the ground too hard",
    "death.attack.fall.player": "%1$s hit the ground too hard whilst trying to escape %2$s",
    "death.attack.flyIntoWall": "%1$s experienced kinetic energy",
    "death.attack.flyIntoWall.player": "%1$s experienced kinetic energy whilst trying to escape %2$s",
    "death.attack.inFire": "%1$s went up in flames",
    "death.attack.inFire.player": "%1$s walked into fire whilst fighting %2$s",
    "death.attack.onFire": "%1$s burned to death",
    "death.attack.onFire.player": "%1$s was burnt to a crisp whilst fighting %2$s",
    "death.attack.onFire.item": "%1$s was burnt to a crisp whilst fighting %2$s wielding %3$s",
    "death.attack.lava": "%1$s tried to swim in lava",
    "death.attack.lava.player": "%1$s tried to swim in lava to escape %2$s",
    "death.attack.Lava": "%1$s tried to swim in lava",
    "death.attack.Lava.player": "%1$s tried to swim in lava to escape %2$s",
    "death.attack.hotFloor": "%1$s discovered the floor was lava",
    "death.attack.hotFloor.player": "%1$s walked into the danger zone due to %2$s",
    "death.attack.inWall": "%1$s suffocated in a wall",
    "death.attack.inWall.player": "%1$s suffocated in a wall whilst fighting %2$s",
    "death.attack.suffocation": "%1$s suffocated in a wall",
    "death.attack.cramming": "%1$s was squished too much",
    "death.attack.cramming.player": "%1$s was squashed by %2$s",
    "death.attack.drown": "%1$s drowned",
    "death.attack.drown.player": "%1$s drowned whilst trying to escape %2$s",
    "death.attack.dryout": "%1$s died from dehydration",
    "death.attack.dryout.player": "%1$s died from dehydration whilst trying to escape %2$s",
    "death.attack.starve": "%1$s starved to death",
    "death.attack.starve.player": "%1$s starved to death whilst fighting %2$s",
    "death.attack.cactus": "%1$s was pricked to death",
    "death.attack.cactus.player": "%1$s walked into a cactus whilst trying to escape %2$s",
    "death.attack.sweetBerryBush": "%1$s was poked to death by a sweet berry bush",
    "death.attack.sweetBerryBush.player": "%1$s was poked to death by a sweet berry bush whilst trying to escape %2$s",
    "death.attack.sting": "%1$s was stung to death",
    "death.attack.sting.player": "%1$s was stung to death by %2$s",
    "death.attack.sting.item": "%1$s was stung to death by %2$s using %3$s",
    "death.attack.freeze": "%1$s froze to death",
    "death.attack.freeze.player": "%1$s was frozen to death by %2$s",
    "death.attack.lightningBolt": "%1$s was struck by lightning",
    "death.attack.lightningBolt.player": "%1$s was struck by lightning whilst fighting %2$s",
    "death.attack.outOfWorld": "%1$s fell out of the world",
    "death.attack.outOfWorld.player": "%1$s didn't want to live in the same world as %2$s",
    "death.attack.outsideBorder": "%1$s left the confines of this world",
    "death.attack.outsideBorder.player": "%1$s left the confines of this world whilst fighting %2$s",
    "death.attack.generic": "%1$s died",
    "death.attack.generic.player": "%1$s died because of %2$s",
    "death.attack.genericKill": "%1$s was killed",
    "death.attack.genericKill.player": "%1$s was killed whilst fighting %2$s",
    "death.attack.magic": "%1$s was killed by magic",
    "death.attack.magic.player": "%1$s was killed by magic whilst trying to escape %2$s",
    "death.attack.indirectMagic": "%1$s was killed by %2$s using magic",
    "death.attack.indirectMagic.item": "%1$s was killed by %2$s using %3$s",
    "death.attack.even_more_magic": "%1$s was killed by even more magic",
    "death.attack.dragonBreath": "%1$s was roasted in dragon breath",
    "death.attack.dragonBreath.player": "%1$s was roasted in dragon breath by %2$s",
    "death.attack.wither": "%1$s withered away",
    "death.attack.wither.player": "%1$s withered away whilst fighting %2$s",
    "death.attack.witherSkull": "%1$s was shot by a skull from %2$s",
    "death.attack.witherSkull.item": "%1$s was shot by a skull from %2$s using %3$s",
    "death.attack.anvil": "%1$s was squashed by a falling anvil",
    "death.attack.anvil.player": "%1$s was squashed by a falling anvil whilst fighting %2$s",
    "death.attack.fallingBlock": "%1$s was squashed by a falling block",
    "death.attack.fallingBlock.player": "%1$s was squashed by a falling block whilst fighting %2$s",
    "death.attack.fallingStalactite": "%1$s was skewered by a falling stalactite",
    "death.attack.fallingStalactite.player": "%1$s was skewered by a falling stalactite whilst fighting %2$s",
    "death.attack.stalagmite": "%1$s was impaled on a stalagmite",
    "death.attack.stalagmite.player": "%1$s was impaled on a stalagmite whilst fighting %2$s",
    "death.attack.fireworks": "%1$s went off with a bang",
    "death.attack.fireworks.player": "%1$s went off with a bang whilst fighting %2$s",
    "death.attack.fireworks.item": "%1$s went off with a bang due to a firework fired from %3$s by %2$s",
    "death.attack.badRespawnPoint.message": "%1$s was killed by %2$s",
    "death.attack.badRespawnPoint.link": "[Intentional Game Design]",
    "death.attack.netherBed.message": "%1$s was killed by %2$s",
    "death.attack.netherBed.link": "[Intentional Game Design]",
    "death.attack.sonic_boom": "%1$s was obliterated by a sonically-charged shriek",
    "death.attack.sonic_boom.player": "%1$s was obliterated by a sonically-charged shriek whilst trying to escape %2$s",
    "death.attack.sonic_boom.item": "%1$s was obliterated by a sonically-charged shriek whilst trying to escape %2$s wielding %3$s",
    "death.attack.mace_smash": "%1$s was smashed by %2$s",
    "death.attack.mace_smash.item": "%1$s was smashed by %2$s with %3$s",
    "death.attack.wind_charge": "%1$s was hit by a wind charge from %2$s",
    "death.attack.wind_charge.item": "%1$s was hit by a wind charge from %2$s using %3$s",
    # --- Whispers, Messages & Team Commands ---
    "commands.message.display.incoming": "%s whispers to you: %s",
    "commands.message.display.outgoing": "You whisper to %s: %s",
    "commands.teammsg.failed.notOnTeam": "You cannot message your team since you are not on a team",
    # --- Admin & Server Commands (commands.*) ---
    "commands.gamemode.success.self": "Set own game mode to %s",
    "commands.gamemode.success.other": "Set %s's game mode to %s",
    "commands.defaultgamemode.success": "The default game mode is now %s",
    "commands.difficulty.query": "The difficulty is %s",
    "commands.difficulty.success": "The difficulty has been set to %s",
    "commands.difficulty.failure": "The difficulty did not change; it is already set to %s",
    "commands.time.set": "Set the time to %s",
    "commands.time.add": "Added %s to the time",
    "commands.time.query": "The time is %s",
    "commands.weather.set.clear": "Set the weather to clear",
    "commands.weather.set.rain": "Set the weather to rain",
    "commands.weather.set.thunder": "Set the weather to rain & thunder",
    "commands.tp.success.entity.single": "Teleported %s to %s",
    "commands.tp.success.entity.multiple": "Teleported %s entities to %s",
    "commands.tp.success.coordinates": "Teleported %s to %s, %s, %s",
    "commands.teleport.success.entity.single": "Teleported %s to %s",
    "commands.teleport.success.entity.multiple": "Teleported %s entities to %s",
    "commands.teleport.success.location.single": "Teleported %s to %s, %s, %s",
    "commands.teleport.success.location.multiple": "Teleported %s entities to %s, %s, %s",
    "commands.give.success.single": "Gave %s %s to %s",
    "commands.give.success.multiple": "Gave %s %s to %s targets",
    "commands.clear.success.single": "Removed %s items from player %s",
    "commands.clear.success.multiple": "Removed %s items from %s players",
    "commands.kill.success.single": "Killed %s",
    "commands.kill.success.multiple": "Killed %s entities",
    "commands.summon.success": "Summoned new %s",
    "commands.effect.give.success.single": "Applied effect %s to %s",
    "commands.effect.clear.everything.success.single": "Removed every effect from %s",
    "commands.enchant.success.single": "Applied enchantment %s to %s's item",
    "commands.op.success": "Made %s a server operator",
    "commands.deop.success": "Made %s no longer a server operator",
    "commands.kick.success": "Kicked %s: %s",
    "commands.ban.success": "Banned %s: %s",
    "commands.pardon.success": "Unbanned %s",
    "commands.whitelist.add.success": "Added %s to the whitelist",
    "commands.whitelist.remove.success": "Removed %s from the whitelist",
    "commands.gamerule.set": "Gamerule %s is now set to: %s",
    "commands.gamerule.query": "Gamerule %s is currently set to: %s",
    "commands.seed.success": "Seed: %s",
    "commands.save.saving": "Saving the game (this may take a moment!)",
    "commands.save.success": "Saved the game",
    "commands.stop.stopping": "Stopping the server",
    "commands.reload.success": "Reloading!",
    "commands.list.players": "There are %s of a max of %s players online: %s",
}


def _load_or_fetch_en_us_translations() -> None:
    """
    Load local en_us.json if present; otherwise attempt a one-time download of the
    official Minecraft en_us.json (6,500+ keys) and merge with MC_TRANSLATIONS.
    """
    global MC_TRANSLATIONS
    lang_path = Path("en_us.json")

    if not lang_path.is_file():
        for url in _LANG_URLS:
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "MCLogger/1.0"},
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    if isinstance(data, dict) and len(data) > 500:
                        lang_path.write_text(raw, encoding="utf-8")
                        log.info(
                            "Downloaded official en_us.json (%d translation keys).",
                            len(data),
                        )
                        break
            except Exception:
                log.debug("Could not fetch en_us.json from %s", url)

    if lang_path.is_file():
        try:
            with lang_path.open(encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    MC_TRANSLATIONS = {**loaded, **MC_TRANSLATIONS}
                    log.info(
                        "Loaded %d total Minecraft translation keys.",
                        len(MC_TRANSLATIONS),
                    )
        except Exception:
            log.warning("Could not parse en_us.json; using built-in translations.")


_FORMAT_SPEC_RE = re.compile(r"%(?:(\d+)\$)?([s%])")
_MC_COLOR_RE = re.compile(r"§[0-9a-fk-orA-FK-OR]")
_HUMANIZE_PREFIXES = (
    "entity.minecraft.",
    "block.minecraft.",
    "item.minecraft.",
    "biome.minecraft.",
    "effect.minecraft.",
    "enchantment.minecraft.",
    "stat.minecraft.",
    "attribute.name.",
)

try:
    _MOVEMENT_PARAMS = set(inspect.signature(MovementInput).parameters.keys())
except Exception:
    _MOVEMENT_PARAMS = {"forward"}


def _encode_varint(value: int) -> bytes:
    buf = bytearray()
    val = value & 0xFFFFFFFF
    while True:
        byte = val & 0x7F
        val >>= 7
        if val != 0:
            buf.append(byte | 0x80)
        else:
            buf.append(byte)
            break
    return bytes(buf)


def _encode_mc_string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return _encode_varint(len(raw)) + raw


class VanillaClientEmulator:
    """
    Emulates real Minecraft Java client protocol packets & hardware input behavior:
    - Sends `minecraft:client_tick_end` at the end of every 50ms physics tick (required by 1.21.2+ / 26.3)
    - Sends `minecraft:player_loaded` once world chunks finish loading (1.21.4+ / 26.3)
    - Sends `minecraft:brand` ("vanilla") and `client_information` (skin layers 0x7F, view distance, locale)
    - Quantizes all yaw/pitch rotations to real Minecraft mouse sensitivity GCD steps
    """

    def __init__(self, version_str: str) -> None:
        self.version_str = version_str.strip()
        # Pick a realistic vanilla mouse sensitivity (e.g., 85% - 115% -> 0.425 to 0.575)
        sens = random.uniform(0.425, 0.575)
        f = 0.6 * sens + 0.2
        self.mouse_gcd: float = (f * f * f) * 8.0 * 0.15

        self._resolved: bool = False
        self._tick_end_id: int | None = None
        self._player_loaded_id: int | None = None
        self._client_info_id: int | None = None
        self._custom_payload_id: int | None = None
        self._tick_end_disabled: bool = False

    def quantize_rotation(
        self,
        cur_yaw: float,
        cur_pitch: float,
        raw_delta_yaw: float,
        raw_delta_pitch: float,
    ) -> tuple[float, float]:
        """Snap rotation deltas to exact vanilla mouse sensitivity GCD steps."""
        gcd = self.mouse_gcd
        if gcd <= 0:
            return (cur_yaw + raw_delta_yaw) % 360.0, max(
                -85.0, min(85.0, cur_pitch + raw_delta_pitch)
            )

        steps_yaw = round(raw_delta_yaw / gcd)
        steps_pitch = round(raw_delta_pitch / gcd)

        new_yaw = (cur_yaw + steps_yaw * gcd) % 360.0
        new_pitch = max(-85.0, min(85.0, cur_pitch + steps_pitch * gcd))
        return new_yaw, new_pitch

    def _resolve_packet_ids(self, bot: Any) -> None:
        if self._resolved:
            return
        self._resolved = True

        version_obj = getattr(bot, "version", None)
        packets = getattr(version_obj, "packets", None)

        def _find_pkt(*names: str) -> int | None:
            if packets is None:
                return None
            for name in names:
                val = getattr(packets, name, None)
                if isinstance(val, int):
                    return val
            return None

        self._tick_end_id = _find_pkt(
            "serverbound_client_tick_end",
            "client_tick_end",
            "serverbound_tick_end",
        )
        self._player_loaded_id = _find_pkt(
            "serverbound_player_loaded",
            "player_loaded",
        )
        self._client_info_id = _find_pkt(
            "serverbound_client_information",
            "client_information",
            "serverbound_client_settings",
            "client_settings",
        )
        self._custom_payload_id = _find_pkt(
            "serverbound_custom_payload",
            "custom_payload",
            "serverbound_plugin_message",
        )

        # Minecraft 26.x (protocol 775) fallback IDs if protobot's packet table omits them
        if self.version_str.startswith("26."):
            if self._tick_end_id is None:
                self._tick_end_id = 0x0E
            if self._player_loaded_id is None:
                self._player_loaded_id = 0x2D

    async def send_join_handshake(self, bot: Any) -> None:
        """Send vanilla brand, client settings, and player_loaded when chunks finish loading."""
        if bot.closed.is_set() or not hasattr(bot, "send_raw"):
            return

        self._resolve_packet_ids(bot)
        sent_features: list[str] = []

        try:
            # 1. minecraft:brand = "vanilla"
            if self._custom_payload_id is not None:
                brand_payload = _encode_mc_string("minecraft:brand") + _encode_mc_string(
                    "vanilla"
                )
                await bot.send_raw(self._custom_payload_id, brand_payload)
                sent_features.append("minecraft:brand")

            # 2. client_information (en_US, view=10, chat=enabled, colors=true, all skin layers=0x7F, right hand=1)
            if self._client_info_id is not None:
                info_payload = (
                    _encode_mc_string("en_US")
                    + struct.pack("b", 10)  # view distance
                    + _encode_varint(0)  # chat mode: enabled
                    + b"\x01"  # chat colors: true
                    + struct.pack("B", 0x7F)  # displayed skin parts: all layers
                    + _encode_varint(1)  # main hand: right
                    + b"\x00"  # enable text filtering: false
                    + b"\x01"  # allow server listings: true
                    + _encode_varint(0)  # particle status: all
                )
                await bot.send_raw(self._client_info_id, info_payload)
                sent_features.append("client_information")

            # 3. player_loaded (tells 1.21.4+ / 26.3 server terrain loading screen closed)
            if self._player_loaded_id is not None:
                await bot.send_raw(self._player_loaded_id, b"")
                sent_features.append("player_loaded")

            if self._tick_end_id is not None:
                sent_features.append(f"client_tick_end(0x{self._tick_end_id:02x})")

            if sent_features:
                log.info(
                    "Vanilla client emulation active: %s (mouse GCD=%.4f°).",
                    ", ".join(sent_features),
                    self.mouse_gcd,
                )
        except Exception:
            log.debug("Optional vanilla join packet skipped.", exc_info=True)

    async def send_tick_end(self, bot: Any) -> None:
        """Emit `minecraft:client_tick_end` at the end of a 50ms client physics tick."""
        if (
            self._tick_end_disabled
            or bot.closed.is_set()
            or not hasattr(bot, "send_raw")
        ):
            return

        self._resolve_packet_ids(bot)
        if self._tick_end_id is None:
            return

        # If protobot already has a native tick_end method, use it
        native_fn = getattr(bot, "send_client_tick_end", None) or getattr(
            bot, "send_tick_end", None
        )
        try:
            if callable(native_fn):
                res = native_fn()
                if inspect.isawaitable(res):
                    await res
            else:
                await bot.send_raw(self._tick_end_id, b"")
        except Exception:
            if not bot.closed.is_set():
                self._tick_end_disabled = True


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
            return key[len(prefix):].replace("_", " ").replace(".", " ").title()

    if key.startswith("advancements.") and key.endswith(".title") and not args:
        slug = key.split(".")[-2]
        return slug.replace("_", " ").title()

    if args:
        return f"{' '.join(arg for arg in args if arg)} ({key})"

    return key


def render_chat_component(component: Any) -> str:
    """Recursively convert a Minecraft chat component into readable text."""
    if component is None:
        return ""
    if isinstance(component, str):
        stripped = component.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (
            stripped.startswith("[") and stripped.endswith("]")
        ):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, (dict, list)):
                    return render_chat_component(parsed)
            except Exception:
                pass
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
    elif component.get("selector") is not None:
        base = str(component["selector"])
    elif component.get("") is not None:
        base = render_chat_component(component[""])

    extra = component.get("extra")
    if isinstance(extra, (list, tuple)):
        base += "".join(render_chat_component(item) for item in extra)

    return _MC_COLOR_RE.sub("", base)


class SmartAFKSession(BotSession):
    """
    Vanilla-emulated Smart AFK session tailored for a 5x3 bedrock enclosure:
    - Emits `client_tick_end` at the end of every 50ms physics tick
    - Quantizes all yaw/pitch changes to real Minecraft mouse sensitivity GCD steps
    - Mixes natural pauses, short walks, strafes, jumps, sneaks, and arm swings
    """

    def __init__(self, config: SessionConfig, credentials, mc_version: str = "26.3"):
        super().__init__(config, credentials=credentials)
        self.emulator = VanillaClientEmulator(mc_version)

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
        log.info("Minecraft vanilla-emulated Smart AFK tick loop started.")

        # Wait until world chunks are loaded before sending movement/physics ticks
        world_event = getattr(bot, "world_ready", None)
        while (
            world_event is not None
            and not world_event.is_set()
            and not bot.closed.is_set()
            and not self._stop.is_set()
        ):
            await asyncio.sleep(0.1)

        if bot.closed.is_set() or self._stop.is_set():
            return

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
                if now >= next_state_change:
                    choice = random.random()
                    if choice < 0.28:
                        forward, strafe, sneak, sprint = 0.0, 0.0, False, False
                        next_state_change = now + random.uniform(1.4, 4.5)
                    elif choice < 0.60:
                        forward = 1.0
                        strafe = random.choice((0.0, 0.0, -0.5, 0.5))
                        sneak = False
                        sprint = random.random() < 0.22
                        next_state_change = now + random.uniform(1.0, 2.8)
                    elif choice < 0.76:
                        forward = random.choice((-1.0, 0.0))
                        strafe = random.choice((-1.0, 1.0)) if forward == 0.0 else 0.0
                        sneak = False
                        sprint = False
                        next_state_change = now + random.uniform(0.8, 2.0)
                    elif choice < 0.90:
                        forward = random.choice((0.0, 0.5, -0.5))
                        strafe = random.choice((0.0, -0.5, 0.5))
                        sneak = True
                        sprint = False
                        next_state_change = now + random.uniform(0.9, 2.4)
                    else:
                        forward = random.choice((0.0, 1.0))
                        strafe = random.choice((0.0, -0.5, 0.5))
                        sneak = False
                        sprint = False
                        jump_until = now + random.uniform(0.25, 0.55)
                        next_state_change = now + random.uniform(1.0, 2.2)

                    if random.random() < 0.20:
                        jump_until = max(jump_until, now + random.uniform(0.15, 0.35))

                jump = now < jump_until

                if now >= next_look_change:
                    cur_yaw = float(getattr(bot.player, "yaw", 0.0))
                    target_yaw = (cur_yaw + random.uniform(-110.0, 110.0)) % 360.0
                    target_pitch = random.uniform(-28.0, 32.0)
                    next_look_change = now + random.uniform(1.4, 4.8)

                try:
                    if not bot.closed.is_set():
                        cur_yaw = float(getattr(bot.player, "yaw", 0.0))
                        cur_pitch = float(getattr(bot.player, "pitch", 0.0))
                        yaw_diff = ((target_yaw - cur_yaw + 180.0) % 360.0) - 180.0
                        pitch_diff = target_pitch - cur_pitch

                        if abs(yaw_diff) > 1.2 or abs(pitch_diff) > 1.2:
                            raw_dyaw = max(-16.0, min(16.0, yaw_diff * 0.32)) + random.uniform(
                                -0.35, 0.35
                            )
                            raw_dpitch = max(
                                -9.0, min(9.0, pitch_diff * 0.32)
                            ) + random.uniform(-0.2, 0.2)

                            # Quantize to real Minecraft mouse sensitivity GCD steps
                            step_yaw, step_pitch = self.emulator.quantize_rotation(
                                cur_yaw,
                                cur_pitch,
                                raw_dyaw,
                                raw_dpitch,
                            )
                            if (
                                abs(step_yaw - cur_yaw) > 1e-4
                                or abs(step_pitch - cur_pitch) > 1e-4
                            ):
                                await bot.send_look(step_yaw, step_pitch)
                except Exception:
                    log.debug("Smart AFK look interpolation skipped.", exc_info=True)

                if now >= next_gesture and not bot.closed.is_set():
                    await self._maybe_player_gesture(bot)
                    next_gesture = now + random.uniform(4.5, 14.0)

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

                try:
                    if not bot.closed.is_set():
                        await bot.tick(
                            _build_movement_input(
                                forward=forward,
                                strafe=strafe,
                                jump=jump,
                                sneak=sneak,
                                sprint=sprint,
                            )
                        )
                        await self.emulator.send_tick_end(bot)
                except Exception:
                    if bot.closed.is_set() or self._stop.is_set():
                        break
                    log.debug("Tick skipped during state transition.", exc_info=True)
            else:
                try:
                    if not bot.closed.is_set():
                        await bot.tick(_build_movement_input())
                        await self.emulator.send_tick_end(bot)
                except Exception:
                    if bot.closed.is_set() or self._stop.is_set():
                        break

            # Natural 1-3ms network jitter around the 50ms (20 TPS) vanilla tick clock
            jitter = random.uniform(-0.0015, 0.0025)
            await asyncio.sleep(max(0.03, self._tick_interval + jitter))

        if self._stop.is_set():
            log.info("Minecraft session is stopping.")


class MinecraftController:
    """Manages the Minecraft connection, random-world guard, and Discord chat bridge."""

    def __init__(
        self,
        discord_client: "MCLoggerDiscord",
        config,
    ):
        self.discord = discord_client
        self.config = config

        try:
            self.max_reconnect_attempts = max(
                1,
                int(os.getenv("MC_RECONNECT_MAX_ATTEMPTS", "400")),
            )
        except ValueError:
            self.max_reconnect_attempts = 400

        self.session: SmartAFKSession | None = None
        self._login_started: set[int] = set()
        self._outgoing_messages: dict[str, float] = {}
        self._explicit_stop: bool = False
        self._watchdog_task: asyncio.Task | None = None
        self._world_guard_task: asyncio.Task | None = None
        self._continuous_attempt: int = 0

    def _create_session(self) -> SmartAFKSession:
        async def offline_credentials():
            return self.config.mc_username, None, None

        session_config = SessionConfig(
            host=self.config.mc_host,
            port=self.config.mc_port,
            version=self.config.mc_version,
            online_mode=False,
            offline_username=self.config.mc_username,
            reconnect=True,
            reconnect_delay=self.config.reconnect_delay,
            reconnect_max_attempts=self.max_reconnect_attempts,
            anti_kick=False,
        )

        session = SmartAFKSession(
            session_config,
            credentials=offline_credentials,
            mc_version=self.config.mc_version,
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
        await asyncio.to_thread(_load_or_fetch_en_us_translations)

        self._explicit_stop = False
        self._continuous_attempt = 0
        self.session = self._create_session()
        self.session.start_background()
        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(
                self._ensure_forever_loop()
            )
        log.info(
            "Minecraft reconnect manager started (pinned to %s:%s, target %d attempts/cycle).",
            self.config.mc_host,
            self.config.mc_port,
            self.max_reconnect_attempts,
        )

    async def _disconnect_foreign_world(self, bot, aternos_status: str) -> None:
        """Force-close a connection that landed on a random shared-port Aternos world."""
        log.warning(
            "Connected to port %s while our Aternos server '%s' is '%s' (foreign/random world)! Disconnecting.",
            self.config.mc_port,
            self.config.mc_host,
            aternos_status,
        )
        await self.discord.log_to_discord(
            f"🛡️ **Random-World Guard:** Port `{self.config.mc_port}` answered, but "
            f"**{self.config.mc_host}** is currently **{aternos_status}** on Aternos. "
            f"Disconnected from the foreign world and waiting for your server."
        )
        try:
            for close_attr in ("close", "disconnect"):
                fn = getattr(bot, close_attr, None)
                if callable(fn):
                    res = fn()
                    if inspect.isawaitable(res):
                        await res
                    break
            bot.closed.set()
        except Exception:
            log.debug("Error closing foreign bot connection.", exc_info=True)

    async def _periodic_world_guard(self, bot) -> None:
        """Every 60s while connected, ensure our Aternos server is still the one online."""
        while not bot.closed.is_set() and not self._explicit_stop:
            await asyncio.sleep(60.0)
            if bot.closed.is_set() or self._explicit_stop:
                break
            is_ours, status_str, _ = await self.discord.aternos.is_our_server_online()
            if not is_ours:
                await self._disconnect_foreign_world(bot, status_str)
                break

    async def _ensure_forever_loop(self) -> None:
        while not self._explicit_stop:
            await asyncio.sleep(max(5.0, float(self.config.reconnect_delay)))
            if self._explicit_stop:
                break
            if self.session is None or not self.session.running:
                if self._continuous_attempt >= self.max_reconnect_attempts:
                    log.info(
                        "Completed %d/%d reconnect attempts; starting a new %d-attempt cycle.",
                        self._continuous_attempt,
                        self.max_reconnect_attempts,
                        self.max_reconnect_attempts,
                    )
                    self._continuous_attempt = 0
                else:
                    log.warning(
                        "Reconnect loop paused at attempt #%d/%d; resuming toward %d.",
                        self._continuous_attempt,
                        self.max_reconnect_attempts,
                        self.max_reconnect_attempts,
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
        if self._world_guard_task is not None and not self._world_guard_task.done():
            self._world_guard_task.cancel()
        if self.session is not None:
            self.session.request_stop()

    async def _on_connecting(self, attempt: int) -> None:
        self._continuous_attempt += 1
        current = self._continuous_attempt

        message = (
            f"Connection attempt #{current}/{self.max_reconnect_attempts} to "
            f"{self.config.mc_host}:{self.config.mc_port}."
        )

        log.info(message)

        await self.discord.log_to_discord(
            f"🔄 {message}"
        )

    async def _on_session_ready(self, bot) -> None:
        # Register listeners immediately so early chat or kick messages are never missed
        bot.on("player_chat", self._on_player_chat)
        bot.on("system_chat", self._on_system_chat)
        bot.on("world_ready", lambda world: self._schedule_login(bot))
        bot.on("error", self._on_bot_error)
        bot.on("close", self._on_bot_close)

        is_ours, aternos_status, _ = await self.discord.aternos.is_our_server_online()
        if not is_ours:
            await self._disconnect_foreign_world(bot, aternos_status)
            return

        if bot.closed.is_set():
            return

        self.discord.aternos.known_banned = False

        log.info("Minecraft connected as %s.", bot.username)

        await self.discord.log_to_discord(
            f"🟢 Minecraft connected as **{bot.username}**."
        )

        if self._world_guard_task is not None and not self._world_guard_task.done():
            self._world_guard_task.cancel()
        self._world_guard_task = asyncio.create_task(self._periodic_world_guard(bot))

        world_event = getattr(bot, "world_ready", None)

        if world_event is not None and world_event.is_set():
            self._schedule_login(bot)

    def _schedule_login(self, bot) -> None:
        if bot.closed.is_set():
            return

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
            is_ours, aternos_status, _ = await self.discord.aternos.is_our_server_online()
            if bot.closed.is_set():
                return
            if not is_ours:
                await self._disconnect_foreign_world(bot, aternos_status)
                return

            if bot.closed.is_set():
                return

            # Send vanilla brand, client settings, and player_loaded packet on terrain load
            if self.session is not None:
                await self.session.emulator.send_join_handshake(bot)

            # Small natural reaction delay (0.4s - 0.9s) before typing /login
            await asyncio.sleep(random.uniform(0.4, 0.9))
            if bot.closed.is_set():
                return

            command = f"/login {self.config.mc_password}"
            await bot.send_command(command)

            log.info("Sent EasyAuth login command.")

            await asyncio.sleep(2.0)

            if not bot.closed.is_set():
                self._continuous_attempt = 0
                bot._mclogger_afk_enabled = True

                log.info("Smart AFK enabled.")

                await self.discord.log_to_discord(
                    "🔐 Minecraft login command sent; Smart AFK enabled."
                )

        except Exception as exc:
            if bot.closed.is_set() or "not open" in str(exc).lower() or isinstance(
                exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)
            ):
                log.info(
                    "Connection closed before EasyAuth login completed; waiting for reconnect."
                )
                return

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
        session = self.session
        bot = session.bot if session is not None else None
        if bot is not None and not getattr(bot, "_mclogger_afk_enabled", False):
            return

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

        session = self.session
        bot = session.bot if session is not None else None
        if bot is not None and not getattr(bot, "_mclogger_afk_enabled", False):
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

        if (
            bot is None
            or bot.closed.is_set()
            or not getattr(bot, "_mclogger_afk_enabled", False)
        ):
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

        current = max(attempt, self._continuous_attempt, 1)
        reason_text = str(reason or "connection closed")

        if "ban" in reason_text.casefold():
            self.discord.aternos.known_banned = True

        log.warning(
            "Minecraft disconnected (attempt #%d/%d): %s",
            current,
            self.max_reconnect_attempts,
            reason_text,
        )

        await self.discord.log_to_discord(
            f"🔴 Minecraft disconnected (attempt **#{current}/{self.max_reconnect_attempts}**): "
            f"`{reason_text[:700]}`. "
            f"Retrying in {self.config.reconnect_delay:g}s."
        )

    async def _on_session_stop(self) -> None:
        log.info("Minecraft reconnect session stopped.")

        if not self._explicit_stop:
            await self.discord.log_to_discord(
                f"🔄 Reconnect cycle continuing (currently at **#{self._continuous_attempt}/{self.max_reconnect_attempts}**)."
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
                f"🟢 Connected as **{bot.username}** "
                "(offline-mode)"
            )

        if self.session.running or not self._explicit_stop:
            return (
                f"🟡 Connecting / waiting to reconnect "
                f"(attempt #{self._continuous_attempt}/{self.max_reconnect_attempts})"
            )

        return "🔴 Offline"
