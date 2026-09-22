import os
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# Указываем Flask, где искать HTML-файлы (в папке templates)
app = Flask(__name__, template_folder='templates')
CORS(app)

# --- НАСТРОЙКИ TELEGRAM ---
TELEGRAM_BOT_TOKEN = "8950844520:AAGuwJtuHRjHpaEU-qhyS08vgwBhomDJ31c"
TELEGRAM_CHAT_ID = "-1004484725748"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram_message(name, phone):
    """Отправляет заявку в группу Telegram"""
    text = (
        "🔔 **Новая заявка с сайта Apex Invest** 🔔\n\n"
        f"👤 **Имя:** `{name}`\n"
        f"📞 **Телефон:** `{phone}`"
    )
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(TELEGRAM_API_URL, data=payload)
        response.raise_for_status()
        return True, response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке в Telegram: {e}")
        return False, str(e)

# --- МАРШРУТЫ ---

@app.route('/', methods=['GET'])
def home():
    """Открывает сам сайт (файл index.html из папки templates)"""
    return render_template('index.html')

@app.route('/api/submit-form', methods=['POST'])
def submit_form():
    """Принимает данные из формы на сайте и шлет в Telegram"""
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON data"}), 400

    name = data.get('name')
    phone = data.get('phone')

    if not name or not phone:
        return jsonify({"status": "error", "message": "Name and phone are required"}), 400

    success, error_info = send_telegram_message(name, phone)

    if success:
        return jsonify({"status": "success", "message": "Data sent to Telegram"}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to send to Telegram", "details": error_info}), 500

# --- ЗАПУСК ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
