from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Хранилище сообщений чата в памяти (для продакшена можно подключить БД)
chat_storage = {}

@app.route('/')
def index():
    return render_template('index.html')

# Поддерживаем оба варианта путей (/api/chat/... и старые /get, /send_message),
# чтобы виджет на сайте гарантированно не выдавал ошибку 404.
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

    # Сохраняем сообщение пользователя в историю
    chat_storage[session_id].append({
        "sender": "user",
        "text": message_text,
        "image": image_data
    })

    return jsonify({
        "status": "success",
        "messages": chat_storage[session_id]
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
