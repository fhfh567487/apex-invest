from flask import Flask, render_template, request, jsonify
import uuid

app = Flask(__name__)

# Хранилище сообщений в памяти (в продакшене используйте БД)
chat_sessions = {}

@app.route('/')
def index():
    return render_template('index.html')

# 1. Маршрут получения сообщений и сессии (исправляет ошибку 404 на скриншоте)
@app.route('/get', methods=['GET'])
def get_messages():
    session_id = request.args.get('session_id')
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    if session_id not in chat_sessions:
        chat_sessions[session_id] = [
            {"sender": "support", "text": "Здравствуйте! Чем мы можем вам помочь?"}
        ]
    
    return jsonify({
        "status": "success",
        "session_id": session_id,
        "messages": chat_sessions[session_id]
    }), 200

# 2. Маршрут для отправки сообщений чата
@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.get_json() or {}
    session_id = data.get('session_id')
    message_text = data.get('message')

    if not message_text:
        return jsonify({"status": "error", "message": "Message text is required"}), 400

    if not session_id or session_id not in chat_sessions:
        session_id = str(uuid.uuid4())
        chat_sessions[session_id] = []

    # Сохраняем сообщение пользователя
    chat_sessions[session_id].append({"sender": "user", "text": message_text})

    # Авто-ответ (при необходимости)
    chat_sessions[session_id].append({
        "sender": "support", 
        "text": "Спасибо за обращение! Оператор ответит вам в ближайшее время."
    })

    return jsonify({
        "status": "success",
        "session_id": session_id,
        "messages": chat_sessions[session_id]
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
