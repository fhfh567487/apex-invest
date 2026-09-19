import os
import random
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
import resend

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")

# Настройка Resend API
resend.api_key = os.getenv("RESEND_API_KEY")

# Временное хранилище кодов подтверждения
verification_codes = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({"success": False, "error": "Email обязателен"}), 400
    
    code = str(random.randint(1000, 9999))
    verification_codes[email] = code
    
    try:
        params = {
            "from": "Apex Invest <onboarding@resend.dev>",
            "to": [email],
            "subject": "Подтверждение регистрации в Apex Invest",
            "html": f"<p>Ваш код подтверждения для регистрации: <b>{code}</b></p>"
        }
        resend.Emails.send(params)
        return jsonify({"success": True, "message": "Код отправлен на почту"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({"success": False, "error": "Email обязателен"}), 400
    
    code = str(random.randint(1000, 9999))
    verification_codes[email] = code
    
    try:
        params = {
            "from": "Apex Invest <onboarding@resend.dev>",
            "to": [email],
            "subject": "Код подтверждения для входа в Apex Invest",
            "html": f"<p>Ваш код для входа: <b>{code}</b></p>"
        }
        resend.Emails.send(params)
        return jsonify({"success": True, "message": "Код отправлен на почту"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.get_json()
    email = data.get('email')
    user_code = data.get('code')
    
    if verification_codes.get(email) == user_code:
        return jsonify({"success": True, "message": "Успешный вход!"})
    return jsonify({"success": False, "error": "Неверный код"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
