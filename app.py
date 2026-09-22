import os
import re
import threading
from flask import Flask, render_template, request, jsonify, render_template_string
import telebot
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SUPPORT_CHAT_ID_RAW = os.getenv("SUPPORT_CHAT_ID")

if not TOKEN or not SUPPORT_CHAT_ID_RAW:
    raise ValueError("Ошибка: BOT_TOKEN и SUPPORT_CHAT_ID должны быть указаны в переменных окружения!")

SUPPORT_CHAT_ID = int(SUPPORT_CHAT_ID_RAW)
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__, static_folder='static', template_folder='templates')

# Хранилище сообщений чата в памяти сервера: { session_id: [ {"sender": "user"/"admin", "text": "..."}, ... ] }
CHAT_STORAGE = {}

# Встроенный интерфейс онлайн-чата (используется, если нет локального index.html)
DEFAULT_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Служба поддержки Apex Invest</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body { background: #0f172a; color: #f8fafc; display: flex; flex-direction: column; height: 100vh; justify-content: center; align-items: center; padding: 20px; }
        .chat-container { width: 100%; max-width: 480px; height: 600px; background: #1e293b; border-radius: 16px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 1px solid #334155; }
        .chat-header { background: #0f172a; padding: 18px; text-align: center; font-weight: 700; font-size: 18px; border-bottom: 1px solid #334155; color: #10b981; }
        .chat-messages { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
        .message { max-width: 82%; padding: 12px 16px; border-radius: 12px; font-size: 14px; line-height: 1.5; word-wrap: break-word; }
        .message.user { background: #2563eb; color: #ffffff; align-self: flex-end; border-bottom-right-radius: 2px; }
        .message.admin { background: #334155; color: #f1f5f9; align-self: flex-start; border-bottom-left-radius: 2px; border: 1px solid #475569; }
        .chat-input { display: flex; padding: 14px; background: #0f172a; gap: 10px; border-top: 1px solid #334155; }
        .chat-input input { flex: 1; padding: 12px 16px; border: 1px solid #334155; border-radius: 8px; background: #1e293b; color: #fff; outline: none; font-size: 14px; }
        .chat-input input:focus { border-color: #10b981; }
        .chat-input button { padding: 12px 20px; border: none; border-radius: 8px; background: #10b981; color: #0f172a; cursor: pointer; font-weight: 700; font-size: 14px; transition: background 0.2s; }
        .chat-input button:hover { background: #059669; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">💬 Служба поддержки Apex Invest</div>
        <div class="chat-messages" id="messages"></div>
        <div class="chat-input">
            <input type="text" id="userInput" placeholder="Напишите сообщение..." onkeydown="if(event.key==='Enter') sendMessage()">
            <button onclick="sendMessage()">Отправить</button>
        </div>
    </div>

    <script>
        let sessionId = localStorage.getItem('chat_session_id');
        if (!sessionId) {
            sessionId = 'user_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('chat_session_id', sessionId);
        }

        let displayedCount = 0;

        async function loadMessages() {
            try {
                const res = await fetch('/api/chat/get?session_id=' + sessionId);
                const data = await res.json();
                const messagesDiv = document.getElementById('messages');
                
                if (data.messages && data.messages.length > displayedCount) {
                    for (let i = displayedCount; i < data.messages.length; i++) {
                        const msg = data.messages[i];
                        const div = document.createElement('div');
                        div.className = 'message ' + msg.sender;
                        div.innerText = (msg.sender === 'admin' ? '👨‍💻 Поддержка: ' : '') + msg.text;
                        messagesDiv.appendChild(div);
                    }
                    displayedCount = data.messages.length;
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                }
            } catch (e) {
                console.error('Ошибка загрузки сообщений:', e);
            }
        }

        async function sendMessage() {
            const input = document.getElementById('userInput');
            const text = input.value.trim();
            if (!text) return;

            input.value = '';
            
            try {
                await fetch('/api/chat/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId, message: text })
                });
                loadMessages();
            } catch (e) {
                alert('Ошибка соединения с сервером');
            }
        }

        setInterval(loadMessages, 2000);
        loadMessages();
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    try:
        return render_template('index.html')
    except Exception:
        return render_template_string(DEFAULT_HTML)

# 1. Прием сообщения от посетителя сайта
@app.route('/api/chat/send', methods=['POST'])
@app.route('/send_message', methods=['POST'])
def send_from_site():
    try:
        data = request.json or request.form or {}
        session_id = data.get('session_id') or data.get('email') or 'user_guest'
        user_text = (data.get('message') or data.get('text') or '').strip()

        if not user_text:
            return jsonify({'error': 'Текст сообщения пуст'}), 400

        if session_id not in CHAT_STORAGE:
            CHAT_STORAGE[session_id] = []

        CHAT_STORAGE[session_id].append({'sender': 'user', 'text': user_text})

        # Карточка обращения в Telegram без капризной разметки Markdown
        support_card = (
            f"💬 Новое сообщение из онлайн-чата!\n\n"
            f"🔑 Сессия: {session_id}\n\n"
            f"✉️ Текст:\n{user_text}"
        )
        bot.send_message(SUPPORT_CHAT_ID, support_card)
        return jsonify({'status': 'ok'})
    except Exception as e:
        print("Ошибка отправки:", e)
        return jsonify({'error': str(e)}), 500

# 2. Получение истории/новых ответов сайтом (опрос каждые 2 секунды)
@app.route('/api/chat/get', methods=['GET'])
def get_for_site():
    session_id = request.args.get('session_id')
    if not session_id or session_id not in CHAT_STORAGE:
        return jsonify({'messages': []})

    return jsonify({'messages': CHAT_STORAGE[session_id]})

# 3. Прием сообщений от пользователей Telegram (/почта)
@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith(('почта', '/почта')))
def handle_telegram_support(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "⚠️ Укажите текст обращения после слова почта.")
        return

    user_text = parts[1].strip()
    username = f"@{message.from_user.username}" if message.from_user.username else "нет"

    support_card = (
        f"📩 Новое обращение из Telegram!\n\n"
        f"👤 Имя: {message.from_user.first_name}\n"
        f"🏷 Юзернейм: {username}\n"
        f"🆔 ID пользователя: {message.from_user.id}\n\n"
        f"💬 Сообщение: {user_text}"
    )
    bot.send_message(SUPPORT_CHAT_ID, support_card)
    bot.reply_to(message, "Ваше сообщение отправлено в поддержку")

# 4. Пересылка вашего ответа из Telegram в чат на сайте или в Telegram пользователю
@bot.message_handler(func=lambda msg: msg.chat.id == SUPPORT_CHAT_ID and msg.reply_to_message is not None)
def handle_admin_reply(message):
    orig_text = message.reply_to_message.text or ""

    # Вариант А: Ответ на сообщение из онлайн-чата сайта
    if "Сессия:" in orig_text:
        try:
            session_id = orig_text.split("Сессия:")[1].split()[0].replace('`', '').strip()

            if session_id not in CHAT_STORAGE:
                CHAT_STORAGE[session_id] = []

            CHAT_STORAGE[session_id].append({'sender': 'admin', 'text': message.text})
            bot.reply_to(message, "✅ Ответ доставлен в чат на сайте!")
            return
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка отправки на сайт: {e}")
            return

    # Вариант Б: Ответ пользователю из Telegram
    if "ID пользователя:" in orig_text:
        try:
            user_id = int(orig_text.split("ID пользователя:")[1].split()[0].replace('`', ''))
            bot.send_message(user_id, f"👨‍💻 Ответ поддержки:\n\n{message.text}")
            bot.reply_to(message, "✅ Ответ переслан в Telegram!")
            return
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка: {e}")
            return

    bot.reply_to(message, "⚠️ Не удалось определить адресата (Сессию сайта или Telegram ID).")

def run_bot():
    print("Бот и сервер поддержки успешно запущены!")
    bot.infinity_polling()

if __name__ == '__main__':
    # Запуск бота в отдельном фоновом потоке
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Запуск Flask на порту Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
