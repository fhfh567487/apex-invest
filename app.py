import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests

# Создаем экземпляр Flask и настраиваем CORS
app = Flask(__name__)
CORS(app)

# Настройки Telegram
TELEGRAM_BOT_TOKEN = "8950844520:AAGuwJtuHRjHpaEU-qhyS08vgwBhomDJ31c"
TELEGRAM_CHAT_ID = "8686442131"


@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')


@app.route('/send_message', methods=['POST'])
def send_message():
    # Поддерживаем как JSON, так и обычные формы (FormData)
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form.to_dict()

    message = data.get('message') or data.get('text')

    if not message:
        return jsonify({'success': False, 'status': 'error', 'message': 'Поле "message" отсутствует'}), 400

    name = data.get('name', 'Аноним')
    contact = data.get('contact', 'Не указан')

    text = (
        f"📩 <b>Новое обращение с сайта!</b>\n\n"
        f"👤 <b>Имя:</b> {name}\n"
        f"📞 <b>Контакт:</b> {contact}\n"
        f"💬 <b>Сообщение:</b>\n{message}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()

        if result.get('ok'):
            # Возвращаем ключи и со статусом, и с success, чтобы JS на сайте точно понял, что всё успешно
            return jsonify({'success': True, 'status': 'success', 'message': 'Отправлено в Telegram'}), 200
        else:
            return jsonify({'success': False, 'status': 'error', 'details': result.get('description')}), 400

    except Exception as e:
        return jsonify({'success': False, 'status': 'error', 'details': str(e)}), 500


# Роут для поддержки, который ожидает фронтенд
@app.route('/api/support', methods=['POST'])
def api_support():
    return send_message()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
