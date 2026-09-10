import os
from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    balance = db.Column(db.Float, default=0.0)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password')

    if not email or not password:
        return jsonify({"status": "error", "message": "Заполните все поля"}), 400

    # Проверка: если пользователь уже есть в базе
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"status": "error", "message": "Этот пользователь уже создан"}), 400

    # Выдаем 100 млн для binarpok@gmail.com
    initial_balance = 100000000.0 if email == 'binarpok@gmail.com' else 0.0

    new_user = User(email=email, password=password, balance=initial_balance)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "status": "success", 
        "message": "Успешная регистрация!", 
        "user_id": new_user.id, 
        "balance": new_user.balance
    }), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password')

    user = User.query.filter_by(email=email, password=password).first()
    if not user:
        return jsonify({"status": "error", "message": "Неверный email или пароль"}), 401

    # Поддерживаем баланс 100 млн при входе
    if email == 'binarpok@gmail.com' and user.balance < 100000000.0:
        user.balance = 100000000.0
        db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Вход выполнен",
        "email": user.email,
        "balance": user.balance
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
