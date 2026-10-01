const { SlashCommandBuilder } = require("discord.js");

module.exports = {
    data: new SlashCommandBuilder()
        .setName("help")
        .setDescription("Show MC Logger commands"),

    async execute(interaction) {
        await interaction.reply(
            "**MC Logger Commands**\n\n" +
            "`/ping` — Check if MC Logger is alive\n" +
            "`/status` — Check Minecraft server status\n" +
            "`/help` — Show this menu"
        );
    },
};