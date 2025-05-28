import telebot
import requests
import urllib.parse
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # Your Telegram user ID

bot = telebot.TeleBot(BOT_TOKEN)

MODELS = ["flux-schnell", "imagen-3-fast", "imagen-3", "recraft-v3"]
RATIOS = ["1:1", "16:9", "9:16", "3:2", "4:3", "5:4"]

# Track usage stats
user_stats = {}

@bot.message_handler(commands=['start', 'help'])
def send_help(message):
    help_text = (
        "👋 *Welcome!*\n\n"
        "Use `/imagen <prompt> <model> <ratio>` to generate images.\n\n"
        "✅ *Available models:* " + ", ".join(MODELS) + "\n"
        "✅ *Available ratios:* " + ", ".join(RATIOS) + "\n\n"
        "📌 *Example:*\n"
        "`/imagen a beautiful landscape imagen-3 16:9`\n\n"
        "💡 *Other commands:*\n"
        "`/stats` → See your usage stats\n"
        "`/help` → Show this help message"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['imagen'])
def handle_imagen(message):
    user_id = message.from_user.id
    params = message.text[len('/imagen '):].strip()
    if not params:
        bot.reply_to(message, "⚠️ Usage: /imagen <prompt> <model> <ratio>")
        return

    parts = params.split()
    if len(parts) < 3:
        bot.reply_to(message, "❌ Error: Please provide all parameters - prompt, model, and ratio")
        return

    prompt = " ".join(parts[:-2])
    model = parts[-2].lower()
    ratio = parts[-1]

    if model not in MODELS:
        bot.reply_to(message, f"❌ Invalid model! Available: {', '.join(MODELS)}")
        return

    if ratio not in RATIOS:
        bot.reply_to(message, f"❌ Invalid ratio! Available: {', '.join(RATIOS)}")
        return

    # Update user stats
    user_stats[user_id] = user_stats.get(user_id, 0) + 1

    bot.send_message(message.chat.id, f"🔄 Generating your image...\n"
                                      f"📝 Prompt: {prompt}\n"
                                      f"🤖 Model: {model}\n"
                                      f"📐 Ratio: {ratio}")

    try:
        encoded_prompt = urllib.parse.quote(prompt)
        api_url = f"https://img.a3z.workers.dev/?prompt={encoded_prompt}&model={model}&ratio={ratio}"
        response = requests.get(api_url)

        if response.status_code == 200:
            bot.send_photo(message.chat.id, api_url,
                           caption=f"🎨 Generated with: {model}\n📐 Ratio: {ratio}")
        else:
            bot.send_message(message.chat.id, f"❌ Error generating image! (Status: {response.status_code})")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['stats'])
def handle_stats(message):
    user_id = message.from_user.id
    count = user_stats.get(user_id, 0)
    bot.reply_to(message, f"📊 You have generated *{count}* images using this bot!", parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        bot.reply_to(message, "❌ You don't have permission to use this command.")
        return

    total_users = len(user_stats)
    total_images = sum(user_stats.values())
    report = f"👑 *Admin Report*\n\n" \
             f"👥 Total users: {total_users}\n" \
             f"🖼 Total images generated: {total_images}\n\n"

    top_users = sorted(user_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    report += "🏆 *Top users:*\n"
    for idx, (uid, count) in enumerate(top_users, 1):
        report += f"{idx}. User ID {uid}: {count} images\n"

    bot.reply_to(message, report, parse_mode="Markdown")

if __name__ == "__main__":
    print("✅ Bot is running...")
    bot.infinity_polling()
