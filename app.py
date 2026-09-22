import os
import threading
from flask import Flask, render_template, request, jsonify, render_template_string
import telebot
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SUPPORT_CHAT_ID_RAW = os.getenv("SUPPORT_CHAT_ID")

if not TOKEN or not SUPPORT_CHAT_ID_RAW:
    raise ValueError("Ошибка: BOT_TOKEN и SUPPORT_CHAT_ID должны быть указаны в переменных окружения!")

SUPPORT_CHAT_ID = int(SUPPORT_CHAT_ID_RAW)
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__, static_folder='static', template_folder='templates')

# Разрешаем CORS (запросы с любых сторонних сайтов и доменов)
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Хранилище сообщений чата: { session_id: [ {"sender": "user"/"admin", "text": "..."}, ... ] }
CHAT_STORAGE = {}

DEFAULT_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Служба поддержки</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }
        body { background: #0f172a; color: #fff; display: flex; flex-direction: column; height: 100vh; justify-content: center; align-items: center; }
        .chat-container { width: 100%; max-width: 450px; height: 550px; background: #1e293b; border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; }
        .chat-header { background: #0f172a; padding: 16px; text-align: center; font-weight: bold; color: #10b981; }
        .chat-messages { flex: 1; padding: 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        .message { max-width: 80%; padding: 10px 14px; border-radius: 10px; font-size: 14px; word-wrap: break-word; }
        .message.user { background: #2563eb; align-self: flex-end; }
        .message.admin { background: #334155; align-self: flex-start; }
        .chat-input { display: flex; padding: 12px; background: #0f172a; gap: 8px; }
        .chat-input input { flex: 1; padding: 10px; border-radius: 6px; border: 1px solid #334155; background: #1e293b; color: #fff; }
        .chat-input button { padding: 10px 16px; border: none; border-radius: 6px; background: #10b981; color: #000; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">💬 Чат поддержки</div>
        <div class="chat-messages" id="messages"></div>
        <div class="chat-input">
            <input type="text" id="userInput" placeholder="Сообщение..." onkeydown="if(event.key==='Enter') sendMessage()">
            <button onclick="sendMessage()">Отправить</button>
        </div>
    </div>
    <script>
        let sessionId = localStorage.getItem('chat_session_id') || 'user_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('chat_session_id', sessionId);
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
                        div.innerText = (msg.sender === 'admin' ? '👨‍💻 ' : '') + msg.text;
                        messagesDiv.appendChild(div);
                    }
                    displayedCount = data.messages.length;
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                }
            } catch (e) {}
        }

        async function sendMessage() {
            const input = document.getElementById('userInput');
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            await fetch('/api/chat/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, message: text })
            });
            loadMessages();
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

# 1. Прием сообщений с любых форм сайта (поддержка POST и OPTIONS)
@app.route('/api/chat/send', methods=['POST', 'OPTIONS'])
@app.route('/send_message', methods=['POST', 'OPTIONS'])
@app.route('/api/support', methods=['POST', 'OPTIONS'])
def send_from_site():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    try:
        data = request.json or request.form or {}
        
        # Получаем данные универсально под любую структуру сайта
        session_id = data.get('session_id') or data.get('email') or data.get('user') or 'user_guest'
        user_text = (data.get('message') or data.get('text') or data.get('msg') or '').strip()

        if not user_text:
            return jsonify({'error': 'Текст сообщения пуст'}), 400

        if session_id not in CHAT_STORAGE:
            CHAT_STORAGE[session_id] = []

        CHAT_STORAGE[session_id].append({'sender': 'user', 'text': user_text})

        # Отправляем в Telegram
        support_card = (
            f"💬 Новое сообщение из онлайн-чата!\n\n"
            f"🔑 Сессия: {session_id}\n\n"
            f"✉️ Текст:\n{user_text}"
        )
        bot.send_message(SUPPORT_CHAT_ID, support_card)
        print(f"[УСПЕХ] Сообщение от {session_id} отправлено в Telegram")
        return jsonify({'status': 'ok', 'message': 'Отправлено'})
    except Exception as e:
        print("[ОШИБКА ОБРАБОТКИ]:", str(e))
        return jsonify({'error': str(e)}), 500

# 2. Получение новых сообщений сайтом
@app.route('/api/chat/get', methods=['GET', 'OPTIONS'])
def get_for_site():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    session_id = request.args.get('session_id')
    if not session_id or session_id not in CHAT_STORAGE:
        return jsonify({'messages': []})

    return jsonify({'messages': CHAT_STORAGE[session_id]})

# 3. Пересылка вашего ответа из Telegram в чат на сайте
@bot.message_handler(func=lambda msg: msg.chat.id == SUPPORT_CHAT_ID and msg.reply_to_message is not None)
def handle_admin_reply(message):
    orig_text = message.reply_to_message.text or ""

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
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
