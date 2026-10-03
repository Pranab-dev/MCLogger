const { SlashCommandBuilder } = require("discord.js");

module.exports = {
    data: new SlashCommandBuilder()
        .setName("about")
        .setDescription("Learn about MC Logger"),

    async execute(interaction) {
        await interaction.reply(
            "**🤖 MC Logger**\n\n" +
            "A Discord ↔ Minecraft bridge built with Node.js.\n\n" +
            "**Features**\n" +
            "• Minecraft → Discord message bridge\n" +
            "• Discord → Minecraft message bridge\n" +
            "• Player join/leave notifications\n" +
            "• Automatic Minecraft reconnection\n" +
            "• Discord slash commands\n" +
            "• LoginSecurity authentication\n\n" +
            "**🛠️ Built with**\n" +
            "Node.js • discord.js • Mineflayer\n\n" +
            "**👨‍💻 Developer**\n" +
            "@thepixelriftx\n\n" +
            "**📦 Version**\n" +
            "1.0.0"
        );
    },
};