import os
import base64
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Хранилище сообщений в памяти
chat_storage = {}

# Автоматически считываем переменные из Environment Variables (Render)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

def send_telegram_notification(session_id, message_text, image_data=None):
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        print("Telegram configuration missing in environment variables.")
        return

    text = f"💬 *Новое сообщение в поддержки Apex Invest!*\n\n👤 *Сессия:* `{session_id}`\n✉️ *Сообщение:* {message_text or '[Изображение/Скриншот]'}"

    # Если отправлен скриншот (base64)
    if image_data and image_data.startswith("data:image"):
        try:
            # Декодируем base64 во временный бинарный файл для отправки фото
            header, encoded = image_data.split(",", 1)
            file_bytes = base64.b64decode(encoded)
            
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            files = {'photo': ('screenshot.png', file_bytes, 'image/png')}
            data = {
                "chat_id": ADMIN_CHAT_ID,
                "caption": text,
                "parse_mode": "Markdown"
            }
            requests.post(url, data=data, files=files, timeout=10)
            return
        except Exception as e:
            print("Error sending photo to Telegram:", e)

    # Если только текстовое сообщение
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Error sending message to Telegram:", e)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/chat/get', methods=['GET'])
@app.route('/get', methods=['GET'])
def get_chat_messages():
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({"status": "error", "message": "Missing session_id"}), 400

    messages = chat_storage.get(session_id, [])
    return jsonify({"status": "success", "messages": messages}), 200


@app.route('/api/chat/send', methods=['POST'])
@app.route('/send_message', methods=['POST'])
def send_chat_message():
    data = request.get_json() or {}
    session_id = data.get('session_id')
    message_text = data.get('message', '')
    image_data = data.get('image', None)

    if not session_id:
        return jsonify({"status": "error", "message": "Missing session_id"}), 400

    if session_id not in chat_storage:
        chat_storage[session_id] = []

    # Сохраняем сообщение пользователя
    chat_storage[session_id].append({
        "sender": "user",
        "text": message_text,
        "image": image_data
    })

    # Отправляем уведомление в Telegram
    send_telegram_notification(session_id, message_text, image_data)

    return jsonify({
        "status": "success",
        "messages": chat_storage[session_id]
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
