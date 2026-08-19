from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Простая база данных в памяти для теста
users_db = []
counter = 100

# Отдаем index.html при открытии http://localhost:5000
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/register', methods=['POST'])
def register():
    global counter
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    for u in users_db:
        if u['email'] == email:
            return jsonify({'success': False, 'message': 'Такой email уже зарегистрирован'}), 400

    counter += 1
    new_user_id = counter
    
    users_db.append({'id': new_user_id, 'email': email, 'password': password})
    
    print(f"[REGISTER SUCCESS] ID: {new_user_id} | Email: {email} | Pass: {password}")

    return jsonify({
        'success': 'True',
        'message': 'Регистрация успешна!',
        'userId': new_user_id
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    for u in users_db:
        if u['email'] == email and u['password'] == password:
            return jsonify({'success': True, 'message': 'Вход выполнен'})
            
    return jsonify({'success': False, 'message': 'Неверный email или пароль'}), 401

if __name__ == '__main__':
    print("Сервер запущен! Откройте в браузере: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)