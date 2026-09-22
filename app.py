import os
import re
import threading
from flask import Flask, render_template, request, jsonify
import telebot
import resend
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SUPPORT_CHAT_ID_RAW = os.getenv("SUPPORT_CHAT_ID")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

if not TOKEN or not SUPPORT_CHAT_ID_RAW:
    raise ValueError("Ошибка: BOT_TOKEN и SUPPORT_CHAT_ID должны быть указаны в переменные окружения!")

SUPPORT_CHAT_ID = int(SUPPORT_CHAT_ID_RAW)
bot = telebot.TeleBot(TOKEN)

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

app = Flask(__name__, static_folder='static', template_folder='templates')

# 1. Отображение главной страницы сайта
@app.route('/')
def home():
    try:
        return render_template('index.html')
    except Exception:
        return "Сайт и бот успешно работают!"

# 2. Прием обращений с формы сайта
@app.route('/send_message', methods=['POST'])
@app.route('/api/support', methods=['POST'])
def handle_web_form():
    data = request.json or request.form
    email = data.get('email') or data.get('user') or 'Не указан'
    name = data.get('name') or 'Аноним'
    msg_text = data.get('message') or data.get('text') or ''

    if not msg_text:
        return jsonify({'error': 'Текст сообщения пуст'}), 400

    support_card = (
        f"📩 **Новое обращение с сайта!**\n\n"
        f"👤 **Имя:** {name}\n"
        f"📧 **Пользователь:** `{email}`\n\n"
        f"💬 **Текст:** {msg_text}"
    )
    bot.send_message(SUPPORT_CHAT_ID, support_card, parse_mode="Markdown")
    return jsonify({'status': 'ok', 'message': 'Сообщение отправлено'})

# 3. Прием обращений из Telegram (/почта)
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith(('почта', '/почта')))
def handle_telegram_support(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "⚠️ Укажите текст обращения после слова почта.")
        return

    user_text = parts[1].strip()
    username = f"@{message.from_user.username}" if message.from_user.username else "нет"

    support_card = (
        f"📩 **Новое обращение из Telegram!**\n\n"
        f"👤 **Имя:** {message.from_user.first_name}\n"
        f"🏷 **Юзернейм:** {username}\n"
        f"🆔 **ID пользователя:** `{message.from_user.id}`\n\n"
        f"💬 **Сообщение:** {user_text}"
    )
    bot.send_message(SUPPORT_CHAT_ID, support_card, parse_mode="Markdown")
    bot.reply_to(message, "Ваше сообщение отправлено в поддержку")

# 4. Пересылка ответа саппорта из Telegram получателю
@bot.message_handler(func=lambda msg: msg.chat.id == SUPPORT_CHAT_ID and msg.reply_to_message is not None)
def handle_admin_reply(message):
    orig_text = message.reply_to_message.text or ""

    # Вариант А: Ответ пользователю в Telegram (по Telegram ID)
    if "ID пользователя:" in orig_text:
        try:
            user_id = int(orig_text.split("ID пользователя:")[1].split()[0].replace('`', ''))
            bot.send_message(user_id, f"👨‍💻 **Ответ от поддержки:**\n\n{message.text}")
            bot.reply_to(message, "✅ Ответ переслан пользователю в Telegram!")
            return
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка отправки в Telegram: {e}")
            return

    # Вариант Б: Ответ пользователю сайта на Email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', orig_text)
    if email_match:
        user_email = email_match.group(0)
        if not RESEND_API_KEY:
            bot.reply_to(message, "❌ Не найден RESEND_API_KEY в настройках Render!")
            return
        try:
            resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": user_email,
                "subject": "Ответ от службы поддержки Apex Invest",
                "html": f"<p>{message.text}</p>"
            })
            bot.reply_to(message, f"✉️ Ответ успешно отправлен на почту {user_email}!")
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка отправки Email: {e}")
        return

    bot.reply_to(message, "⚠️ Не удалось найти Telegram ID или Email в сообщении.")

def run_bot():
    print("Бот и сервер поддержки успешно запущены!")
    bot.infinity_polling()

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
