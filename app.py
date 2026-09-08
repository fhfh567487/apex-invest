from flask import Flask, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

# --- НАСТРОЙКИ SMTP ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_EMAIL = "your_email@gmail.com"
SENDER_PASSWORD = "your_app_password"  # Пароль приложения (для Gmail/Yandex/Mail.ru)


def send_withdrawal_email(to_email: str, amount: str | float, wallet_address: str) -> bool:
    """Функция формирования и отправки email-уведомления"""
    subject = "Заявка на вывод средств принята"
    body = (
        f"Здравствуйте!\n\n"
        f"Ваша заявка на вывод средств успешно сформирована и передана в обработку.\n\n"
        f"Детали заявки:\n"
        f"- Сумма: {amount}\n"
        f"- Реквизиты/Кошелек: {wallet_address}\n\n"
        f"Если вы не совершали эту операцию, срочно обратитесь в поддержку."
    )

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка отправки письма: {e}")
        return False


@app.route('/api/withdraw', methods=['POST'])
def handle_withdrawal():
    data = request.get_json()

    if not data:
        return jsonify({"status": "error", "message": "Тело запроса должно быть в формате JSON"}), 400

    email = data.get('email')
    amount = data.get('amount')
    wallet = data.get('wallet')

    if not all([email, amount, wallet]):
        return jsonify({
            "status": "error", 
            "message": "Заполните все обязательные поля: email, amount, wallet"
        }), 400

    # 1. Здесь выполняется логика сохранения в БД (например, db.session.add(...))

    # 2. Отправка письма сразу после логики вывода
    is_sent = send_withdrawal_email(
        to_email=email,
        amount=amount,
        wallet_address=wallet
    )

    if is_sent:
        return jsonify({
            "status": "success",
            "message": "Заявка создана, уведомление отправлено на почту."
        }), 200
    else:
        return jsonify({
            "status": "warning",
            "message": "Заявка создана, но не удалось отправить письмо на почту."
        }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
