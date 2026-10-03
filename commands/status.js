const { SlashCommandBuilder } = require("discord.js");

module.exports = {
    data: new SlashCommandBuilder()
        .setName("status")
        .setDescription("Check the Minecraft server status"),

    async execute(interaction) {
        const { mcConnected, mcBot } = require("../index");

        if (mcConnected && mcBot) {
            await interaction.reply(
                "🟢 **Minecraft: Connected**\n" +
                `🤖 **Bot:** ${mcBot.username}\n` +
                "🌐 **Server:** thenexus.aternos.me:32552"
            );
        } else {
            await interaction.reply(
                "🔴 **Minecraft: Offline / Disconnected**\n" +
                "MC Logger is currently not connected to the Minecraft server."
            );
        }
    },
};