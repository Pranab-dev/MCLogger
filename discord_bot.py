from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request

import discord
from discord import app_commands
from discord.ext import commands

from aternos_manager import AternosManager
from minecraft import MinecraftController

log = logging.getLogger("mclogger.discord")

BOT_ACTIVITY_NAME = "Playing Nexus SMP!"


class MCLoggerDiscord(commands.Bot):
    def __init__(self, config):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            status=discord.Status.online,
            activity=discord.Game(name=BOT_ACTIVITY_NAME),
        )

        self.config = config
        self.aternos = AternosManager(config)
        self.minecraft = MinecraftController(self, config)
        self.restart_requested: bool = False

    async def _apply_permanent_presence(self) -> None:
        """Keep the bot's Discord status locked to 'Playing Nexus SMP!'."""
        if self.is_closed():
            return
        try:
            await self.change_presence(
                status=discord.Status.online,
                activity=discord.Game(name=BOT_ACTIVITY_NAME),
            )
        except Exception:
            log.debug("Could not update Discord presence.", exc_info=True)

    def _is_eligible_admin(self, interaction: discord.Interaction) -> bool:
        """Return True if the user is in ADMIN_USER_IDS, is Server Owner, or has Administrator perms."""
        user = interaction.user
        if user.id in self.config.admin_user_ids:
            return True

        if interaction.guild is not None:
            if interaction.guild.owner_id == user.id:
                return True
            if isinstance(user, discord.Member) and user.guild_permissions.administrator:
                return True

        return False

    def _has_panel_config(self) -> bool:
        key = self.config.panel_api_key
        srv = self.config.panel_server_id
        if not (self.config.panel_url and key and srv):
            return False
        if "your_" in key.lower() or "your_" in srv.lower():
            return False
        return True

    def _send_panel_restart_sync(self) -> tuple[bool, str]:
        """Send a container restart power signal to the Silly Development (Pterodactyl) Panel."""
        url = (
            f"{self.config.panel_url}/api/client/servers/"
            f"{self.config.panel_server_id}/power"
        )
        payload = json.dumps({"signal": "restart"}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.panel_api_key}",
                "Accept": "Application/vnd.pterodactyl.v1+json",
                "Content-Type": "application/json",
                "User-Agent": "MCLogger/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 202, 204):
                    return True, "Panel accepted restart signal."
                return False, f"Unexpected HTTP status {resp.status}"
        except urllib.error.HTTPError as exc:
            return False, f"HTTP {exc.code}: {exc.reason}"
        except Exception as exc:
            return False, str(exc)

    async def setup_hook(self) -> None:
        # -----------------------------------------------------
        # Slash commands
        # -----------------------------------------------------

        async def ping(interaction: discord.Interaction):
            await interaction.response.send_message(
                "🏓 Pong!",
                ephemeral=True,
            )

        async def status(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            mc_status = self.minecraft.status_text()
            aternos_status, ban_status = await self.aternos.get_status_report()

            await interaction.followup.send(
                f"**MC Logger Status**\n"
                f"Discord: 🟢 Online\n"
                f"Minecraft Bot: {mc_status}\n"
                f"Aternos Server: {aternos_status}\n"
                f"Ban Status: {ban_status}",
                ephemeral=True,
            )

        async def start_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=False)

            ok, message = await self.aternos.start_server()
            await interaction.followup.send(message)

            if ok:
                await self.log_to_discord(
                    f"🚀 **{interaction.user}** triggered `/start` for `{self.config.mc_host}`."
                )

        async def unban_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=False)

            ok, message = await self.aternos.unban_mclogger()
            await interaction.followup.send(message)

            if ok:
                await self.log_to_discord(
                    f"🔓 **{interaction.user}** unbanned **{self.config.mc_username}** via `/unban`."
                )

        async def restart_command(interaction: discord.Interaction):
            if not self._is_eligible_admin(interaction):
                await interaction.response.send_message(
                    "⛔ Only the server owner or eligible administrators can restart the MCLogger backend.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                "🔄 Restarting MCLogger backend now...",
                ephemeral=False,
            )

            await self.log_to_discord(
                f"🔄 Backend restart triggered by **{interaction.user}** (`{interaction.user.id}`)."
            )

            asyncio.create_task(self._restart_backend())

        async def about_command(interaction: discord.Interaction):
            await interaction.response.send_message(
                "**🤖 About MCLogger**\n"
                "MCLogger is a 24/7 Minecraft-to-Discord bridge and automated server companion. "
                "It relays live in-game chat, join/leave logs, advancements, deaths, and admin notices "
                "directly to Discord, keeps your server active with human-like Smart AFK movement, "
                "and lets you manage Aternos startups and unbans right from Discord.\n\n"
                "👨‍💻 **Developer:** `@thepixelriftx`\n"
                "🔗 **GitHub Repository:** https://github.com/Pranab-dev/MCLogger",
                ephemeral=True,
            )

        async def help_command(interaction: discord.Interaction):
            await interaction.response.send_message(
                "**MC Logger commands**\n"
                "`/ping` — Check Discord bot response.\n"
                "`/status` — Check Discord, Minecraft, Aternos server, and Ban status.\n"
                "`/start` — Start the Aternos server.\n"
                "`/unban` — Unban MCLogger on Aternos if it is currently banned.\n"
                "`/restart` — Restart the MCLogger backend (Owner / Admin only).\n"
                "`/about` — View information about MCLogger, its developer, and GitHub repo.\n"
                "`/help` — Show this command list.\n\n"
                "Send a message in the configured Minecraft channel "
                "to relay it in-game.",
                ephemeral=True,
            )

        self.tree.add_command(
            app_commands.Command(
                name="ping",
                description="Check whether MC Logger is responding.",
                callback=ping,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="status",
                description="Show Discord, Minecraft, Aternos, and Ban status.",
                callback=status,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="start",
                description="Start the Aternos Minecraft server.",
                callback=start_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="unban",
                description="Unban MCLogger on Aternos if banned by policy.",
                callback=unban_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="restart",
                description="Restart the MCLogger backend (Owner / Admin only).",
                callback=restart_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="about",
                description="About MCLogger, developer info, and GitHub repository.",
                callback=about_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="help",
                description="Show the MC Logger command list.",
                callback=help_command,
            )
        )

        # Start Minecraft connection manager.
        await self.minecraft.start()

        # Synchronize Discord slash commands.
        await self.tree.sync()

    async def _restart_backend(self) -> None:
        """
        Mark restart_requested = True and close the client so main.py re-execs
        the process in-place without stopping the Silly Development container.
        """
        await asyncio.sleep(1.0)
        self.restart_requested = True

        if self._has_panel_config():
            ok, detail = await asyncio.to_thread(self._send_panel_restart_sync)
            if ok:
                log.info("Silly Development panel restart signal sent (%s).", detail)
            else:
                log.warning(
                    "Panel restart request failed (%s); using in-place process restart.",
                    detail,
                )

        await self.close()

    async def on_ready(self) -> None:
        await self._apply_permanent_presence()

        log.info(
            "Discord connected as %s.",
            self.user,
        )

        await self.log_to_discord(
            f"🤖 MC Logger Discord bot online as **{self.user}**."
        )

    async def on_resumed(self) -> None:
        await self._apply_permanent_presence()

    # ---------------------------------------------------------
    # Discord -> Minecraft
    # ---------------------------------------------------------

    async def on_message(
        self,
        message: discord.Message,
    ) -> None:
        if message.author.bot or message.guild is None:
            return

        if message.channel.id != self.config.minecraft_channel_id:
            return

        content = message.content.strip()

        if not content:
            return

        content = content[:200]

        sent = await self.minecraft.send_discord_chat(
            str(message.author.display_name),
            content,
        )

        if not sent:
            try:
                await message.add_reaction("⚠️")
            except discord.HTTPException:
                log.exception(
                    "Could not add failure reaction to Discord message."
                )

    # ---------------------------------------------------------
    # Minecraft -> Discord
    # ---------------------------------------------------------

    async def send_minecraft_chat(
        self,
        content: str,
    ) -> bool:
        if self.is_closed():
            return False

        channel = await self._get_text_channel(
            self.config.minecraft_channel_id
        )

        if channel is None:
            log.warning(
                "Minecraft chat Discord channel is unavailable."
            )
            return False

        content = str(content).strip()

        if not content:
            return False

        content = discord.utils.escape_mentions(content)

        chunks = [
            content[index:index + 1900]
            for index in range(0, len(content), 1900)
        ]

        try:
            for chunk in chunks:
                if self.is_closed():
                    return False
                await channel.send(
                    chunk,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            return True

        except (discord.HTTPException, RuntimeError):
            if not self.is_closed():
                log.exception(
                    "Could not send Minecraft chat to Discord."
                )
            return False

    # ---------------------------------------------------------
    # Operational logs -> Bot log Discord channel
    # ---------------------------------------------------------

    async def log_to_discord(
        self,
        content: str,
    ) -> bool:
        if self.is_closed():
            return False

        channel = await self._get_text_channel(
            self.config.bot_log_channel_id
        )

        if channel is None:
            log.warning(
                "Bot log Discord channel is unavailable."
            )
            return False

        try:
            await channel.send(
                str(content)[:1900],
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return True

        except (discord.HTTPException, RuntimeError):
            if not self.is_closed():
                log.exception(
                    "Could not send operational log to Discord."
                )
            return False

    # ---------------------------------------------------------
    # Discord channel lookup
    # ---------------------------------------------------------

    async def _get_text_channel(self, channel_id: int):
        if self.is_closed():
            return None

        channel = self.get_channel(channel_id)

        if channel is None:
            try:
                channel = await self.fetch_channel(channel_id)

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
                RuntimeError,
            ):
                return None

        if isinstance(
            channel,
            (discord.TextChannel, discord.Thread),
        ):
            return channel

        return None

    # ---------------------------------------------------------
    # Shutdown
    # ---------------------------------------------------------

    async def close(self) -> None:
        await self.minecraft.stop()
        await super().close()
