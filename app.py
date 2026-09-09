from flask import Flask, request, jsonify, render_template
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

@app.route('/')
def index():
    return render_template('index.html')

# Защита от повторной регистрации на одну почту
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password')

    if not email or not password:
        return jsonify({"status": "error", "message": "Заполните все поля"}), 400

    # Проверка: существует ли уже такой email в БД
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"status": "error", "message": "Пользователь с таким email уже зарегистрирован!"}), 400

    new_user = User(email=email, password=password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"status": "success", "message": "Успешная регистрация!"}), 201

# Эндпоинт для автосинхронизации данных между ПК и телефоном
@app.route('/api/user/status', methods=['GET'])
def get_status():
    # В реальной системе данные берутся по ID текущей сессии пользователя
    user = User.query.first()
    if user:
        return jsonify({
            "status": "success",
            "email": user.email,
            "balance": user.balance
        })
    return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
