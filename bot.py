import telebot
import sqlite3
import threading
from collections import deque

BOT_TOKEN = "7990422644:AAGfq9wZcbyWlzVP1WDv0HNu5GRruCqAcWs"  # Replace with your bot token
ADMIN_IDS = [7176592290]  # Replace with your Telegram user ID(s)

bot = telebot.TeleBot(BOT_TOKEN)

# Database setup
conn = sqlite3.connect('botdata.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    blocked INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS chats (
    user_id INTEGER PRIMARY KEY,
    partner_id INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER,
    reported_id INTEGER,
    reason TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

conn.commit()
lock = threading.Lock()

waiting_queue = deque()

def is_blocked(user_id):
    with lock:
        cursor.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
        row = cursor.fetchone()
    return row and row[0] == 1

def add_user_if_not_exists(user_id):
    with lock:
        cursor.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
        conn.commit()

def set_chat(user1, user2):
    with lock:
        cursor.execute("REPLACE INTO chats(user_id, partner_id) VALUES (?, ?)", (user1, user2))
        cursor.execute("REPLACE INTO chats(user_id, partner_id) VALUES (?, ?)", (user2, user1))
        conn.commit()

def remove_chat(user_id):
    with lock:
        cursor.execute("SELECT partner_id FROM chats WHERE user_id=?", (user_id,))
        partner = cursor.fetchone()
        if partner:
            partner_id = partner[0]
            cursor.execute("DELETE FROM chats WHERE user_id=?", (user_id,))
            cursor.execute("DELETE FROM chats WHERE user_id=?", (partner_id,))
            conn.commit()
            return partner_id
        else:
            return None

def get_partner(user_id):
    with lock:
        cursor.execute("SELECT partner_id FROM chats WHERE user_id=?", (user_id,))
        partner = cursor.fetchone()
    return partner[0] if partner else None

def find_partner(user_id):
    if is_blocked(user_id):
        return None
    add_user_if_not_exists(user_id)
    existing_partner = get_partner(user_id)
    if existing_partner:
        return existing_partner

    while waiting_queue:
        partner_id = waiting_queue.popleft()
        if partner_id != user_id and not is_blocked(partner_id) and get_partner(partner_id) is None:
            set_chat(user_id, partner_id)
            return partner_id

    waiting_queue.append(user_id)
    return None

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    partner = find_partner(user_id)
    if partner:
        bot.send_message(user_id, "🤝 Partner found! Say hi anonymously.")
        bot.send_message(partner, "🤝 Partner found! Say hi anonymously.")
    else:
        bot.send_message(user_id, "⏳ Waiting for a partner... Send /stop to cancel.")

@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    user_id = message.from_user.id
    partner = remove_chat(user_id)
    if partner:
        bot.send_message(user_id, "🛑 Chat ended.")
        bot.send_message(partner, "🛑 Your partner ended the chat.")
    else:
        if user_id in waiting_queue:
            try:
                waiting_queue.remove(user_id)
            except ValueError:
                pass
            bot.send_message(user_id, "❌ You canceled the waiting.")
        else:
            bot.send_message(user_id, "ℹ️ You are not in a chat or waiting queue.")

@bot.message_handler(commands=['next'])
def cmd_next(message):
    cmd_stop(message)
    cmd_start(message)

@bot.message_handler(commands=['help'])
def cmd_help(message):
    help_text = """
Welcome to Anonymous Chat Bot!

Commands:
/start - Find a partner to chat anonymously
/stop - End current chat or cancel waiting
/next - Skip current partner and find new one
/report <reason> - Report your partner for abuse
/block - Block your current partner
/unblock <user_id> - Unblock a user (admin only)
/stats - Show bot stats (admin only)

Enjoy anonymous chatting! 🤖
"""
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['report'])
def cmd_report(message):
    user_id = message.from_user.id
    partner_id = get_partner(user_id)
    if not partner_id:
        bot.send_message(user_id, "ℹ️ You are not chatting with anyone.")
        return

    reason = message.text[len('/report'):].strip()
    if not reason:
        bot.send_message(user_id, "❗ Please provide a reason after /report command.")
        return

    with lock:
        cursor.execute("INSERT INTO reports (reporter_id, reported_id, reason) VALUES (?, ?, ?)", (user_id, partner_id, reason))
        conn.commit()
    bot.send_message(user_id, "✅ Report sent to admin. Thank you!")

@bot.message_handler(commands=['block'])
def cmd_block(message):
    user_id = message.from_user.id
    partner_id = get_partner(user_id)
    if not partner_id:
        bot.send_message(user_id, "ℹ️ You are not chatting with anyone.")
        return

    with lock:
        cursor.execute("UPDATE users SET blocked=1 WHERE user_id=?", (partner_id,))
        conn.commit()
    remove_chat(user_id)
    bot.send_message(user_id, "🚫 User blocked and chat ended.")
    bot.send_message(partner_id, "⚠️ You have been blocked and disconnected.")

@bot.message_handler(commands=['unblock'])
def cmd_unblock(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "❌ You are not authorized to use this command.")
        return

    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "Usage: /unblock <user_id>")
        return

    try:
        user_to_unblock = int(parts[1])
    except ValueError:
        bot.send_message(message.chat.id, "User ID must be a number.")
        return

    with lock:
        cursor.execute("UPDATE users SET blocked=0 WHERE user_id=?", (user_to_unblock,))
        conn.commit()
    bot.send_message(message.chat.id, f"✅ User {user_to_unblock} unblocked.")

@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "❌ You are not authorized to use this command.")
        return

    with lock:
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM chats")
        total_chats = cursor.fetchone()[0] // 2
        cursor.execute("SELECT COUNT(*) FROM reports")
        total_reports = cursor.fetchone()[0]

    bot.send_message(message.chat.id,
                     f"📊 Bot Stats:\nUsers: {total_users}\nActive chats: {total_chats}\nReports: {total_reports}")

@bot.message_handler(func=lambda m: True)
def relay(message):
    user_id = message.from_user.id
    partner_id = get_partner(user_id)
    if not partner_id:
        bot.send_message(user_id, "ℹ️ You are not connected. Use /start to find a partner.")
        return

    if is_blocked(user_id) or is_blocked(partner_id):
        bot.send_message(user_id, "⚠️ Chat not available due to block status.")
        remove_chat(user_id)
        return

    try:
        if message.content_type == 'text':
            bot.send_message(partner_id, message.text)
        elif message.content_type == 'photo':
            bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)
        elif message.content_type == 'sticker':
            bot.send_sticker(partner_id, message.sticker.file_id)
        elif message.content_type == 'video':
            bot.send_video(partner_id, message.video.file_id, caption=message.caption)
        else:
            bot.send_message(user_id, "⚠️ Unsupported message type.")
    except Exception as e:
        bot.send_message(user_id, "⚠️ Failed to send message to partner.")

if __name__ == "__main__":
    print("Bot started...")
    bot.infinity_polling()
