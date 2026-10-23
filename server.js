from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ====================== АВТОМАТИЧЕСКИЕ ПОЛЬЗОВАТЕЛИ (свои имена) ======================
def create_automatic_users():
    """Создаёт 3 уникальных пользователя автоматически при старте"""
    users = [
        {"nickname": "alex***99", "balance": 5000, "email": "alex99@invest.com"},
        {"nickname": "crypto***king", "balance": 12000, "email": "crypto@invest.com"},
        {"nickname": "invest***77", "balance": 8000, "email": "invest77@invest.com"}
    ]
    
    for user in users:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM users WHERE nickname = ?", (user["nickname"],))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO users (nickname, balance, email, created_at)
                    VALUES (?, ?, ?, ?)
                """, (user["nickname"], user["balance"], user["email"], datetime.now()))
                conn.commit()
                print(f"✅ Авто-создан пользователь: {user['nickname']}")
            else:
                print(f"ℹ️ Пользователь {user['nickname']} уже есть")
        except Exception as e:
            print(f"❌ Ошибка при создании {user['nickname']}: {e}")

# Простая база данных в памяти для теста (как было в оригинале)
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
        'success': True,
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

# ====================== АВТОМАТИЧЕСКИЕ ПОЛЬЗОВАТЕЛИ + ТРАНЗАКЦИИ ======================
def init_db():
    """Создаёт таблицу transactions с username (чтобы в "Последних транзакциях" были настоящие ники)"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            payment_system TEXT,
            status TEXT,
            created_at TEXT,
            username TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_transaction(user_id, transaction_type, amount, payment_system, status="Завершено"):
    """Автоматически добавляет транзакцию с ником пользователя"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    username = get_user_nickname(user_id)  # берём ник из таблицы users
    
    cursor.execute("""
        INSERT INTO transactions 
        (user_id, type, amount, payment_system, status, created_at, username)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, transaction_type, amount, payment_system, status, datetime.now().isoformat(), username))
    
    conn.commit()
    conn.close()
    print(f"✅ Транзакция добавлена для {username}: {transaction_type} ${amount}")

def get_user_nickname(user_id):
    """Получаем ник по user_id"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT nickname FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else f"user_{user_id}"

# Вызываем автосоздание пользователей при старте
init_db()
create_automatic_users()
# =====================================================================================

if __name__ == '__main__':
    print("Сервер запущен! Откройте в браузере: http://localhost:5000")
    print("Автоматические пользователи созданы!")
    app.run(host='0.0.0', port=5000, debug=True)
