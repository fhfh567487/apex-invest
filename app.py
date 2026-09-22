import os
import threading
from flask import Flask
import telebot
from dotenv import load_dotenv

# Загрузка переменных из .env файла
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SUPPORT_CHAT_ID_RAW = os.getenv("SUPPORT_CHAT_ID")

if not TOKEN or not SUPPORT_CHAT_ID_RAW:
    raise ValueError("Ошибка: переменные BOT_TOKEN и SUPPORT_CHAT_ID должны быть указаны")

SUPPORT_CHAT_ID = int(SUPPORT_CHAT_ID_RAW)
bot = telebot.TeleBot(TOKEN)

# Веб-сервер Flask для удовлетворения проверок Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@bot.message_handler(func=lambda msg: msg.text and msg.text.lower().startswith(('почта', '/почта')))
def handle_support_request(message):
    parts = message.text.split(maxsplit=1)
    
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(
            message, 
            "⚠️ Ошибка: укажите текст сообщения!\n"
            "Пример: `почта Не могу войти в аккаунт`",
            parse_mode="Markdown"
        )
        return

    user_text = parts[1].strip()
    username = f"@{message.from_user.username}" if message.from_user.username else "нет"
    
    support_card = (
        f"📩 **Новое обращение!**\n"
        f"👤 **Имя:** {message.from_user.first_name}\n"
        f"🏷 **Юзернейм:** {username}\n"
        f"🆔 **ID пользователя:** `{message.from_user.id}`\n\n"
        f"💬 **Сообщение:**\n{user_text}"
    )

    bot.send_message(SUPPORT_CHAT_ID, support_card, parse_mode="Markdown")
    bot.reply_to(message, "Ваше сообщение отправлено в поддержку")

@bot.message_handler(func=lambda msg: msg.chat.id == SUPPORT_CHAT_ID and msg.reply_to_message is not None)
def handle_admin_reply(message):
    try:
        orig_text = message.reply_to_message.text
        
        if "ID пользователя:" in orig_text:
            user_id = int(orig_text.split("ID пользователя:")[1].split()[0].replace('`', ''))
            
            bot.send_message(
                user_id, 
                f"👨‍💻 **Ответ от поддержки:**\n\n{message.text}"
            )
            bot.reply_to(message, "✅ Ответ переслан пользователю!")
    except Exception as e:
        bot.reply_to(message, f"❌ Не удалось переслать ответ. Ошибка: {e}")

def run_bot():
    print("Бот поддержки успешно запущен!")
    bot.infinity_polling()

if __name__ == '__main__':
    # Запускаем бота в отдельном фоновом потоке
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Запускаем веб-сервер на порту, который предоставляет Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)