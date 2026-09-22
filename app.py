import os
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__, template_folder='templates')
CORS(app)

# --- НАСТРОЙКИ TELEGRAM ---
TELEGRAM_BOT_TOKEN = "8950844520:AAGuwJtuHRjHpaEU-qhyS08vgwBhomDJ31c"
TELEGRAM_CHAT_ID = "-1004484725748"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram_message(text_content):
    """Универсальная отправка сообщения в Telegram"""
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text_content,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(TELEGRAM_API_URL, data=payload)
        response.raise_for_status()
        return True, response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке в Telegram: {e}")
        return False, str(e)

# --- МАРШРУТЫ САЙТА И API ---

@app.route('/', methods=['GET'])
def home():
    """Главная страница сайта (index.html)"""
    return render_template('index.html')

@app.route('/api/submit-form', methods=['POST'])
def submit_form():
    """Обработчик обычной формы заявки"""
    data = request.json or request.form
    name = data.get('name', 'Не указано')
    phone = data.get('phone', 'Не указано')

    message = (
        "🔔 **Новая заявка с сайта Apex Invest**\n\n"
        f"👤 **Имя:** `{name}`\n"
        f"📞 **Телефон:** `{phone}`"
    )

    success, error = send_telegram_message(message)
    if success:
        return jsonify({"status": "success", "message": "Sent!"}), 200
    return jsonify({"status": "error", "message": str(error)}), 500

@app.route('/api/support', methods=['POST'])
def support_form():
    """Обработчик формы поддержки (как на вашем скриншоте с сообщением 'Ку')"""
    data = request.json or request.form
    # Поддерживаем разные варианты ключей из фронтенда (message, text, query)
    user_message = data.get('message') or data.get('text') or data.get('query') or str(data)

    message = (
        "💬 **Сообщение в поддержку Apex**\n\n"
        f"📝 **Текст:**\n`{user_message}`"
    )

    success, error = send_telegram_message(message)
    if success:
        return jsonify({"status": "success", "message": "Sent!"}), 200
    return jsonify({"status": "error", "message": str(error)}), 500

# --- ЗАПУСК ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
