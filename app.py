from flask import Flask, render_template, request, jsonify, session, redirect, url_for[cite: 4]
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'apex_invest_secret_key'
DB_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 1000.0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin/add_money', methods=['POST'])
def admin_add_money():
    email = request.form.get('email')
    try:
        amount = float(request.form.get('amount'))
    except (TypeError, ValueError):
        return "Ошибка: неверная сумма!", 400

    # Используем встроенную функцию подключения к БД
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Безопасно обновляем баланс (прибавляем к текущему значению)
    cursor.execute("""
        UPDATE users 
        SET balance = balance + ? 
        WHERE email = ?
    """, (amount, email))
    
    conn.commit()
    conn.close()

    # Перенаправляем обратно в админку (убедитесь, что функция называется admin_panel)
    return redirect(url_for('admin_panel'))

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({"success": False, "message": "Заполните все поля!"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Пользователь уже существует!"}), 400

    hashed_password = generate_password_hash(password)
    cursor.execute("INSERT INTO users (email, password, balance) VALUES (?, ?, ?)", 
                   (email, hashed_password, 1000.0))
    conn.commit()
    session['user_id'] = cursor.lastrowid
    conn.close()
    
    return jsonify({"success": True, "message": "Регистрация успешна!"})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        return jsonify({"success": True, "message": "Успешный вход!"})
    
    return jsonify({"success": False, "message": "Неверный email или пароль!"}), 401

@app.route('/api/user_data', methods=['GET'])
def get_user_data():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False}), 401

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email, balance FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        return jsonify({"success": True, "user": {"email": user["email"], "balance": user["balance"]}})
    return jsonify({"success": False}), 404

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
