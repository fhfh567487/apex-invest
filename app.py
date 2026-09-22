import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
# Включаем CORS для всех доменов, чтобы сайт мог отправлять запросы
CORS(app)

# --- НАСТРОЙКИ TELEGRAM ---
# Ваш токен бота (проверьте, что он совпадает с тем, что вы создавали в BotFather)
TELEGRAM_BOT_TOKEN = "8950844520:AAGuwJtuHRjHpaEU-qhyS08vgwBhomDJ31c"
# ID вашей группы (тот, который вы прислали ранее)
TELEGRAM_CHAT_ID = "-1004484725748"

# Базовый URL для API Telegram
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def send_telegram_message(name, phone):
    """Отправляет форматированное сообщение в Telegram"""
    text = (
        "🔔 **Новая заявка с сайта Apex Invest** 🔔\n\n"
        f"👤 **Имя:** `{name}`\n"
        f"📞 **Телефон:** `{phone}`"
    )

    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'Markdown' # Используем Markdown для жирного текста и моноширинного шрифта
    }

    try:
        response = requests.post(TELEGRAM_API_URL, data=payload)
        # Если API Telegram вернул ошибку, вызываем исключение
        response.raise_for_status()
        return True, response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке в Telegram: {e}")
        return False, str(e)


# --- МАРШРУТЫ (API ENDPOINTS) ---

@app.route('/', methods=['GET'])
def health_check():
    """Простая проверка, что сервер работает"""
    return jsonify({"status": "ok", "message": "Backend is running"}), 200


@app.route('/api/submit-form', methods=['POST'])
def submit_form():
    """Обработчик формы"""
    # Получаем данные из JSON-запроса, который отправляет ваш сайт
    data = request.json

    # Проверка: если данных нет или они не в формате JSON
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON data"}), 400

    # Извлекаем имя и телефон
    name = data.get('name')
    phone = data.get('phone')

    # Валидация: проверяем, что поля заполнены
    if not name or not phone:
        return jsonify({"status": "error", "message": "Name and phone are required"}), 400

    # Отправляем данные в Telegram
    success, error_info = send_telegram_message(name, phone)

    if success:
        return jsonify({"status": "success", "message": "Data sent to Telegram"}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to send to Telegram", "details": error_info}), 500


# --- ЗАПУСК СЕРВЕРА ---
if __name__ == '__main__':
    # Render обычно устанавливает порт в переменной окружения PORT
    port = int(os.environ.get('PORT', 10000))
    # Запускаем Flask на всех интерфейсах (0.0.0.0)
    app.run(host='0.0.0.0', port=port)
