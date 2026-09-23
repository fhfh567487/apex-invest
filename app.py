import os
import threading
import base64
from io import BytesIO
from flask import Flask, render_template, request, jsonify
import telebot
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SUPPORT_CHAT_ID_RAW = os.getenv("SUPPORT_CHAT_ID")

if not TOKEN or not SUPPORT_CHAT_ID_RAW:
    raise ValueError("Ошибка: BOT_TOKEN и SUPPORT_CHAT_ID должны быть указаны в переменных окружения!")

SUPPORT_CHAT_ID = int(SUPPORT_CHAT_ID_RAW)
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__, static_folder='static', template_folder='templates')

# Разрешаем CORS
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Хранилище сообщений чата в памяти
CHAT_STORAGE = {}

@app.route('/')
def home():
    try:
        return render_template('index.html')
    except Exception:
        return "Сайт и бот поддержки запущены!"

# Прием сообщения или скриншота от пользователя
@app.route('/api/chat/send', methods=['POST', 'OPTIONS'])
@app.route('/send_message', methods=['POST', 'OPTIONS'])
@app.route('/api/support', methods=['POST', 'OPTIONS'])
def send_from_site():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    try:
        data = request.json or request.form or {}
        session_id = data.get('session_id') or data.get('email') or 'user_guest'
        user_text = (data.get('message') or data.get('text') or '').strip()
        image_data = data.get('image')

        if not user_text and not image_data:
            return jsonify({'error': 'Сообщение пустое'}), 400

        if session_id not in CHAT_STORAGE:
            CHAT_STORAGE[session_id] = []

        msg_obj = {'sender': 'user', 'text': user_text}
        if image_data:
            msg_obj['image'] = image_data
        CHAT_STORAGE[session_id].append(msg_obj)

        if image_data:
            header, encoded = image_data.split(",", 1) if "," in image_data else ("", image_data)
            img_bytes = base64.b64decode(encoded)
            photo_file = BytesIO(img_bytes)
            photo_file.name = "screenshot.jpg"

            caption = (
                f"💬 Скриншот из онлайн-чата!\n\n"
                f"🔑 Сессия: {session_id}\n\n"
                f"✉️ Текст: {user_text if user_text else 'Без текста'}"
            )
            bot.send_photo(SUPPORT_CHAT_ID, photo_file, caption=caption)
        else:
            support_card = (
                f"💬 Новое сообщение из онлайн-чата!\n\n"
                f"🔑 Сессия: {session_id}\n\n"
                f"✉️ Текст:\n{user_text}"
            )
            bot.send_message(SUPPORT_CHAT_ID, support_card)

        return jsonify({'status': 'ok', 'message': 'Отправлено'})
    except Exception as e:
        print("[ОШИБКА ОБРАБОТКИ]:", str(e))
        return jsonify({'error': str(e)}), 500

# Получение истории сообщений сайтом
@app.route('/api/chat/get', methods=['GET', 'OPTIONS'])
def get_for_site():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    session_id = request.args.get('session_id')
    if not session_id or session_id not in CHAT_STORAGE:
        return jsonify({'messages': []})

    return jsonify({'messages': CHAT_STORAGE[session_id]})

# Пересылка ответа из Telegram обратно на сайт
@bot.message_handler(func=lambda msg: msg.chat.id == SUPPORT_CHAT_ID and msg.reply_to_message is not None)
def handle_admin_reply(message):
    orig_text = message.reply_to_message.text or message.reply_to_message.caption or ""

    if "Сессия:" in orig_text:
        try:
            session_id = orig_text.split("Сессия:")[1].split()[0].replace('`', '').strip()

            if session_id not in CHAT_STORAGE:
                CHAT_STORAGE[session_id] = []

            CHAT_STORAGE[session_id].append({'sender': 'admin', 'text': message.text})
            bot.reply_to(message, "✅ Ответ доставлен в чат на сайте!")
            return
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка отправки на сайт: {e}")
            return

    bot.reply_to(message, "⚠️ Не удалось определить сессию сайта.")

def run_bot():
    print("Бот и сервер поддержки успешно запущены!")
    bot.infinity_polling()

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
