import os
import urllib.parse
import requests
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext

# Define allowed models and ratios
MODELS = ["flux-schnell", "imagen-3-fast", "imagen-3", "recraft-v3"]
RATIOS = ["1:1", "16:9", "9:16", "3:2", "4:3", "5:4"]

# Get the Telegram bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("⚠️ BOT_TOKEN environment variable not set!")

def imagen_command(update: Update, context: CallbackContext) -> None:
    args = context.args

    if not args or len(args) < 3:
        update.message.reply_text(
            "⚠️ *Usage:* /imagen <prompt> <model> <ratio>\n\n"
            f"🔹 *Example:* /imagen a beautiful landscape imagen-3 16:9\n\n"
            f"📌 *Available models:* {', '.join(MODELS)}\n"
            f"📐 *Available ratios:* {', '.join(RATIOS)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    prompt = " ".join(args[:-2]).strip()
    model = args[-2].lower()
    ratio = args[-1]

    if model not in MODELS:
        update.message.reply_text(f"❌ *Invalid model!*\nAvailable: {', '.join(MODELS)}", parse_mode=ParseMode.MARKDOWN)
        return

    if ratio not in RATIOS:
        update.message.reply_text(f"❌ *Invalid ratio!*\nAvailable: {', '.join(RATIOS)}", parse_mode=ParseMode.MARKDOWN)
        return

    processing_msg = update.message.reply_text(
        f"🔄 *Generating your image...*\n"
        f"📝 *Prompt:* _{prompt}_\n"
        f"🤖 *Model:* `{model}`\n"
        f"📐 *Ratio:* {ratio}",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        encoded_prompt = urllib.parse.quote_plus(prompt)
        api_url = f"https://img.a3z.workers.dev/?prompt={encoded_prompt}&model={model}&ratio={ratio}"

        context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")

        response = requests.get(api_url)

        if response.status_code == 200:
            context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=api_url,
                caption=f"🎨 *Generated with:* _{model}_\n📐 *Ratio:* {ratio}",
                parse_mode=ParseMode.MARKDOWN
            )
            context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg.message_id)
        else:
            context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=processing_msg.message_id,
                text=f"❌ *Error generating image!* (Status: {response.status_code})",
                parse_mode=ParseMode.MARKDOWN
            )

    except Exception as e:
        context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=f"❌ *Error:* {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("imagen", imagen_command))

    print("🤖 Bot is running...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
