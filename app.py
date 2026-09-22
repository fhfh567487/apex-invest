import os
import threading
from flask import Flask, render_template, request, jsonify
import telebot
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SUPPORT_CHAT_ID_RAW = os.getenv("SUPPORT_CHAT_ID")

if not TOKEN or not SUPPORT_CHAT_ID_RAW:
    raise ValueError("Ошибка: BOT_TOKEN и SUPPORT_CHAT_ID должны быть указаны!")

SUPPORT_CHAT_ID = int(SUPPORT_CHAT_ID_RAW)
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__, static_folder='static', template_folder='templates')

# Хранилище сообщений чата в памяти сайта: { session_id: [ {"sender": "user"/"admin", "text": "..."}, ... ] }
CHAT_STORAGE = {}

@app.route('/')
def home():
    try:
        return render_template('index.html')
    except Exception:
        return "Сайт и бот функционируют!"

# 1. Прием сообщения от посетителя сайта
@app.route('/api/chat/send', methods=['POST'])
def send_from_site():
    data = request.json or {}
    session_id = data.get('session_id')
    user_text = data.get('message', '').strip()

    if not session_id or not user_text:
        return jsonify({'error': 'Заполните текст сообщения'}), 400

    if session_id not in CHAT_STORAGE:
        CHAT_STORAGE[session_id] = []

    # Сохраняем сообщение клиента
    CHAT_STORAGE[session_id].append({'sender': 'user', 'text': user_text})

    # Отправляем карточку в Telegram
    support_card = (
        f"💬 **Новое сообщение из онлайн-чата!**\n\n"
        f"🔑 **Сессия:** `{session_id}`\n\n"
        f"✉️ **Текст:**\n{user_text}"
    )
    bot.send_message(SUPPORT_CHAT_ID, support_card, parse_mode="Markdown")
    return jsonify({'status': 'ok'})

# 2. Получение истории/новых ответов сайтом (опрос сервера)
@app.route('/api/chat/get', methods=['GET'])
def get_for_site():
    session_id = request.args.get('session_id')
    if not session_id or session_id not in CHAT_STORAGE:
        return jsonify({'messages': []})

    return jsonify({'messages': CHAT_STORAGE[session_id]})

# 3. Пересылка вашего ответа из Telegram прямо в чат на сайте
@bot.message_handler(func=lambda msg: msg.chat.id == SUPPORT_CHAT_ID and msg.reply_to_message is not None)
def handle_admin_reply(message):
    orig_text = message.reply_to_message.text or ""

    # Если ответ идет на сообщение из онлайн-чата сайта
    if "Сессия:" in orig_text:
        try:
            # Извлекаем ID сессии сайта
            session_id = orig_text.split("Сессия:")[1].split()[0].replace('`', '').strip()

            if session_id not in CHAT_STORAGE:
                CHAT_STORAGE[session_id] = []

            # Добавляем ответ оператора в чат пользователю
            CHAT_STORAGE[session_id].append({'sender': 'admin', 'text': message.text})
            bot.reply_to(message, "✅ Ответ отправлен прямо в чат на сайте!")
            return
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка отправки на сайт: {e}")
            return

    # Если ответ идет пользователю, который написал из самого Telegram
    if "ID пользователя:" in orig_text:
        try:
            user_id = int(orig_text.split("ID пользователя:")[1].split()[0].replace('`', ''))
            bot.send_message(user_id, f"👨‍💻 **Ответ поддержки:**\n\n{message.text}")
            bot.reply_to(message, "✅ Ответ переслан в Telegram!")
            return
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка: {e}")
            return

    bot.reply_to(message, "⚠️ Не удалось найти Сессию сайта или Telegram ID.")

def run_bot():
    print("Бот и онлайн-чат запущены!")
    bot.infinity_polling()

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
