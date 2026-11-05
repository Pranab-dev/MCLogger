from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from minecraft import MinecraftController

log = logging.getLogger("mclogger.discord")


class MCLoggerDiscord(commands.Bot):
    def __init__(self, config):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

        self.config = config
        self.minecraft = MinecraftController(self, config)

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
            mc_status = self.minecraft.status_text()

            await interaction.response.send_message(
                f"**MC Logger Status**\n"
                f"Discord: 🟢 Online\n"
                f"Minecraft: {mc_status}",
                ephemeral=True,
            )

        async def help_command(interaction: discord.Interaction):
            await interaction.response.send_message(
                "**MC Logger commands**\n"
                "`/ping` — Check Discord bot response.\n"
                "`/status` — Check Discord and Minecraft status.\n"
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
                description="Show Discord and Minecraft status.",
                callback=status,
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

    async def on_ready(self) -> None:
        log.info(
            "Discord connected as %s.",
            self.user,
        )

        await self.log_to_discord(
            f"🤖 MC Logger Discord bot online as **{self.user}**."
        )

    # ---------------------------------------------------------
    # Discord -> Minecraft
    # ---------------------------------------------------------

    async def on_message(
        self,
        message: discord.Message,
    ) -> None:
        if message.author.bot or message.guild is None:
            return

        # Only messages in the configured Minecraft channel
        # are sent into Minecraft.
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
        """
        Send Minecraft chat-window content to the normal
        Minecraft Discord channel.

        This function deliberately does NOT use bot_log_channel_id.
        """

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

        # Prevent Minecraft text from triggering Discord mentions.
        content = discord.utils.escape_mentions(content)

        # Discord's message limit is 2000 characters.
        # Split long system messages instead of silently truncating.
        chunks = [
            content[index:index + 1900]
            for index in range(0, len(content), 1900)
        ]

        try:
            for chunk in chunks:
                await channel.send(
                    chunk,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            return True

        except discord.HTTPException:
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

        except discord.HTTPException:
            log.exception(
                "Could not send operational log to Discord."
            )
            return False

    # ---------------------------------------------------------
    # Discord channel lookup
    # ---------------------------------------------------------

    async def _get_text_channel(self, channel_id: int):
        channel = self.get_channel(channel_id)

        if channel is None:
            try:
                channel = await self.fetch_channel(channel_id)

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
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