import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
import resend

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")

# Настройка Resend API
resend.api_key = os.getenv("RESEND_API_KEY")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({"success": False, "error": "Email обязателен"}), 400
    
    try:
        params = {
            "from": "Apex Invest <onboarding@resend.dev>",
            "to": [email],
            "subject": "Подтверждение регистрации в Apex Invest",
            "html": "<p>Спасибо за регистрацию в Apex Invest! Добро пожаловать на платформу.</p>"
        }
        email_response = resend.Emails.send(params)
        return jsonify({"success": True, "response": email_response})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
