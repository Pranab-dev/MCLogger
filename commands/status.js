const { SlashCommandBuilder } = require("discord.js");

module.exports = {
    data: new SlashCommandBuilder()
        .setName("status")
        .setDescription("Check the Minecraft server status"),

    async execute(interaction) {
        await interaction.reply(
            "Minecraft server status: **Not connected yet** 🔴"
        );
    },
};