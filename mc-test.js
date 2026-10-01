const mineflayer = require("mineflayer");

const PASSWORD = "PUT_A_NEW_BOT_PASSWORD_HERE";

const bot = mineflayer.createBot({
    host: "Friend_AI.aternos.me",
    port: 32552,
    username: "MCLogger",
    version: false
});

bot.once("spawn", () => {
    console.log("MC Logger joined Minecraft! 🟢");

    // Give LoginSecurity a moment to show its login/register screen
    setTimeout(() => {
        console.log("Sending registration command...");
        bot.chat(`/login ${PASSWORD}`);
    }, 2000);
});

bot.on("messagestr", (message) => {
    console.log(`[MC MESSAGE] ${message}`);
});

bot.on("chat", (username, message) => {
    console.log(`[MC CHAT] ${username}: ${message}`);
});

bot.on("kicked", (reason) => {
    console.log("\n========== BOT KICKED ==========");
    console.log(JSON.stringify(reason, null, 2));
    console.log("================================\n");
});

bot.on("error", (err) => {
    console.error("\nMinecraft error:", err);
});

bot.on("end", (reason) => {
    console.log("\nConnection ended:", reason);
});