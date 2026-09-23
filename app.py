import os
import sqlite3
import threading
import secrets
from flask import Flask, render_template, request, jsonify, redirect, url_for
import telebot
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "Appexinvestet_bot")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "apex_secret_key_123")

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            telegram_chat_id INTEGER,
            auth_token TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- ИНИЦИАЛИЗАЦИЯ TELEGRAM БОТА ---
bot = None
if BOT_TOKEN:
    try:
        bot = telebot.TeleBot(BOT_TOKEN)
        print("✅ Telegram bot initialized")
    except Exception as e:
        print(f"❌ Error initializing bot: {e}")

if bot:
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        chat_id = message.chat.id
        args = message.text.split()

        # Если перешли по ссылке вида /start <token>
        if len(args) > 1:
            auth_token = args[1]
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            # Ищем пользователя с таким токеном
            cursor.execute("SELECT id, username FROM users WHERE auth_token = ?", (auth_token,))
            user = cursor.fetchone()

            if user:
                user_id, username = user
                # Привязываем telegram_chat_id и сбрасываем одноразовый токен
                cursor.execute("UPDATE users SET telegram_chat_id = ?, auth_token = NULL WHERE id = ?", (chat_id, user_id))
                conn.commit()
                conn.close()

                welcome_msg = (
                    f"🎉 *Аккаунт Apex успешно привязан!*\n\n"
                    f"Здравствуйте, *{username}*! Теперь вы будете получать мгновенные "
                    f"уведомления о пополнениях, выводах и входах в аккаунт."
                )
                bot.reply_to(message, welcome_msg, parse_mode="Markdown")
                return
            conn.close()

        # Обычный запуск /start без параметра
        bot.reply_to(
            message,
            "👋 *Добро пожаловать в Apex Invest Bot!*\n\n"
            "Чтобы привязать аккаунт, нажмите кнопку *«Подключить бота»* в личном кабинете на сайте.",
            parse_mode="Markdown"
        )

    def run_bot():
        print("🚀 Telegram bot polling started...")
        bot.infinity_polling(skip_pending=True)

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

# --- ВЕБ-МАРШРУТЫ (FLASK) ---

@app.route("/")
def home():
    return render_template("index.html")

# API для получения ссылки с кодом привязки бота
@app.route("/api/telegram/connect", methods=["POST"])
def connect_telegram():
    data = request.json or {}
    user_id = data.get("user_id", 1)  # Замените на ID из вашей системы авторизации/сессии

    # Генерируем уникальный токен авторизации
    auth_token = secrets.token_hex(8)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET auth_token = ? WHERE id = ?", (auth_token, user_id))
    conn.commit()
    conn.close()

    deep_link = f"https://t.me/{BOT_USERNAME}?start={auth_token}"
    return jsonify({"success": True, "link": deep_link})

# API для отправки Push-уведомления пользователю в Telegram
@app.route("/api/notify", methods=["POST"])
def notify_user():
    data = request.json or {}
    user_id = data.get("user_id")
    text = data.get("message")

    if not user_id or not text:
        return jsonify({"success": False, "error": "user_id and message are required"}), 400

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_chat_id FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        return jsonify({"success": False, "error": "Telegram not linked for this user"}), 404

    chat_id = row[0]

    if bot:
        try:
            bot.send_message(chat_id, text, parse_mode="Markdown")
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": False, "error": "Bot is not active"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
