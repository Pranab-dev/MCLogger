const { SlashCommandBuilder } = require("discord.js");

module.exports = {
    data: new SlashCommandBuilder()
        .setName("ping")
        .setDescription("Check if MC Logger is online"),

    async execute(interaction) {
        await interaction.reply("Pong! 🟢");
    },
};