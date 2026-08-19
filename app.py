import os
import sqlite3
from flask import Flask, request, jsonify, send_file, render_template

app = Flask(__name__)

# Фиксируем точный путь к базе данных в папке проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return send_file('index.html')

# МАРШРУТ АДМИНКИ: достаем пользователей и передаем их в шаблон
@app.route('/admin')
def admin_page():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Позволяет брать данные по именам колонок
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, password FROM users')
    all_users = cursor.fetchall()
    conn.close()
    
    # Передаем список пользователей прямо в admin.html
    return render_template('admin.html', users=all_users)

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', 
                       (username, email, password))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Регистрация успешна'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Такой email уже зарегистрирован'})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM users WHERE email = ? AND password = ?', (email, password))
    user = cursor.fetchone()
    conn.close()

    if user:
        return jsonify({'success': True, 'username': user[0]})
    else:
        return jsonify({'success': False, 'message': 'Неверный email или пароль'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)