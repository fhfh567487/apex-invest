from flask import Flask, request, jsonify, render_template, g
import sqlite3

app = Flask(__name__, template_folder='.') # Ищет HTML файл в той же папке

DATABASE = 'users.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Автоматическое создание таблицы, если её нет
def init_db():
    with app.app_context():
        db = get_db()
        db.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
        db.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')

    db = get_db()
    # Ищем пользователя в базе
    existing_user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if existing_user:
        return jsonify({"error": "Такой аккаунт уже есть. Пожалуйста, выполните вход."}), 400
    else:
        db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        db.commit()
        return jsonify({"success": "Аккаунт успешно создан!"}), 200

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()

    if user:
        return jsonify({"success": "Вы успешно вошли в систему!"}), 200
    else:
        return jsonify({"error": "Неверный логин или пароль"}), 400

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
