@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.get_json()

    if not data or 'message' not in data:
        return jsonify({'status': 'error', 'message': 'Поле "message" отсутствует'}), 400

    name = data.get('name', 'Аноним')
    contact = data.get('contact', 'Не указан')
    message = data.get('message')

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
            return jsonify({'status': 'success', 'message': 'Отправлено в Telegram'}), 200
        else:
            return jsonify({'status': 'error', 'details': result.get('description')}), 500

    except Exception as e:
        return jsonify({'status': 'error', 'details': str(e)}), 500

# Добавляем дублирующий роут для поддержки фронтенда
@app.route('/api/support', methods=['POST'])
def api_support():
    return send_message()
