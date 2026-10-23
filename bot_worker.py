import os
import sys
import time
import telebot
from telebot import types
from dotenv import load_dotenv
import database as db

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "Appexinvestet_bot")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# Конфигурация планов прибыли
PLAN_CONFIGS = {
    "Novice": {"days": 1, "daily_pct": 0.12},
    "Pro": {"days": 10, "daily_pct": 0.25},
    "Master": {"days": 30, "daily_pct": 0.15},
}

if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN not set")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# --- Вспомогательные функции ---

def calc_today_profit(user_data):
    if not user_data: return 0.0
    transactions = user_data.get("transactions") or []
    today_profit = 0.0
    for tx in transactions:
        if tx.get("type") != "DEPOSIT": continue
        if tx.get("status") in ("Completed", "Paid") or tx.get("payoutProcessed"): continue
        plan = tx.get("plan") or "Novice"
        config = PLAN_CONFIGS.get(plan, {"daily_pct": 0.12})
        daily_pct = tx.get("dailyPct") or config["daily_pct"]
        amount = float(tx.get("amount") or 0)
        today_profit += amount * daily_pct
    return today_profit

def format_balance_message(email, user_data):
    if not isinstance(user_data, dict): user_data = {}
    balance = float(user_data.get("balance") or 0)
    total_profit = float(user_data.get("totalProfit") or 0)
    total_invested = float(user_data.get("totalInvested") or 0)
    active = int(user_data.get("activeDeposits") or 0)
    today = calc_today_profit(user_data)

    name = ""
    if user_data.get("firstName") or user_data.get("lastName"):
        name = f"{user_data.get('firstName', '')} {user_//data.get('lastName', '')}".strip()

    lines = []
    if name: lines.append(f"👤 {name}")
    lines.append(f"📧 {email}")
    lines.append("")
    lines.append(f"💰 Баланс: ${balance:.2f}")
    lines.append(f"📈 Всего заработано: ${total_profit:.2f}")
    lines.append(f"📅 За сегодня: ${today:.2f}")
    lines.append(f"📦 Вложено: ${total_invested:.2f}")
    lines.append(f"🟢 Активных депозитов: {active}")
    return "\n".join(lines)

def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("💰 Баланс", "📈 Заработок")
    kb.row("🔗 Привязать аккаунт", "🚪 Отвязать")
    kb.row("💬 Поддержка", "📖 Помощь")
    return kb

def cancel_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("❌ Отмена")
    return kb

def verify_login_supabase(email, password):
    from database import supabase_request
    email = email.strip().lower()
    password = password.strip()

    params = {"username": f"eq.{email}", "select": "username,password,user_data"}
    data = supabase_request("tradepiramid", params=params)

    if not data: return {"error": "not_found"}
    row = data[0]
    if str(row.get("password") or "") != password:
        return {"error": "bad_password"}
    return {"ok": True, "username": row.get("username"), "user_data": row.get("user_data")}

# --- Handlers ---

@bot.message_handler(commands=["start"])
def handle_start(message):
    chat_id = message.chat.id
    db.clear_link_state(chat_id)

    linked = db.get_user_by_chat_id(chat_id)
    if linked:
        email = linked['username']
        user_data = db.fetch_user_data_from_supabase(email) or {}
        bot.send_message(chat_id, f"👋 Снова здравствуйте!\n\nАккаунт: `{email}`\n\nВыберите действие:",
                         parse_mode="Markdown", reply_markup=main_keyboard())
        bot.send_message(chat_id, format_balance_message(email, user_data), reply_markup=main_keyboard())
        return

    args = message.text.split(maxsplit=1)
    payload = args[1].strip() if len(args) > 1 else ""

    if payload:
        payload_lower = payload.lower()
        token_user = db.get_user_by_auth_token(payload)
        if token_user:
            email = token_user['username']
            db.link_user_by_email(email, chat_id)
            user_data = db.fetch_user_data_from_supabase(email) or {}
            bot.send_message(chat_id, f"✅ Аккаунт привязан!\n\nEmail: `{email}`", parse_mode="Markdown", reply_markup=main_keyboard())
            bot.send_message(chat_id, format_balance_message(email, user_data), reply_markup=main_keyboard())
            return

        if payload_lower == "link":
            db.set_link_state(chat_id, "email")
            bot.reply_to(message, "📧 Введите email от аккаунта Apex Invest:", reply_markup=cancel_keyboard())
            return

    bot.reply_to(message, "👋 Добро пожаловать в Apex Invest Bot!\n\nПривяжите аккаунт, чтобы смотреть баланс.", reply_markup=main_keyboard())

@bot.message_handler(commands=["balance", "bal"])
@bot.message_handler(func=lambda m: m.text in ("💰 Баланс", "Баланс"))
def handle_balance(message):
    chat_id = message.chat.id
    if db.get_link_state(chat_id): return

    user = db.get_user_by_chat_id(chat_id)
    if not user:
        bot.reply_to(message, "❌ Аккаунт не привязан.", reply_markup=main_keyboard())
        return

    email = user['username']
    user_data = db.fetch_user_data_from_supabase(email)
    if user_data is None:
        bot.reply_to(message, "⚠️ Ошибка загрузки данных.", reply_markup=main_keyboard())
        return

    bot.reply_to(message, format_balance_message(email, user_data), reply_markup=main_keyboard())

@bot.message_handler(commands=["earn", "profit", "today"])
@bot.message_handler(func=lambda m: m.text in ("📈 Заработок", "Заработок"))
def handle_earnings(message):
    chat_id = message.chat.id
    if db.get_link_state(chat_id): return

    user = db.get_user_by_chat_id(chat_id)
    if not user:
        bot.reply_to(message, "❌ Аккаунт не привязан.", reply_markup=main_keyboard())
        return

    email = user['username']
    user_data = db.fetch_user_data_from_supabase(email)
    if user_data is None:
        bot.reply_to(message, "⚠️ Ошибка загрузки данных.", reply_markup=main_keyboard())
        return

    total_profit = float(user_data.get("totalProfit") or 0)
    today = calc_today_profit(user_data)
    balance = float(user_data.get("balance") or 0)

    text = f"📈 Заработок\n\n📅 За сегодня: ${today:.2f}\n💎 Всего: ${total_profit:.2f}\n💰 Баланс: ${balance:.2f}"
    bot.reply_to(message, text, reply_markup=main_keyboard())

@bot.message_handler(commands=["link", "login"])
@bot.message_handler(func=lambda m: m.text in ("🔗 Привязать аккаунт", "Привязать аккаунт"))
def start_link(message):
    db.set_link_state(message.chat.id, "email")
    bot.reply_to(message, "📧 Введите email от аккаунта:", reply_markup=cancel_keyboard())

@bot.message_handler(func=lambda m: m.text in ("❌ Отмена", "Отмена"))
def cancel_link(message):
    db.clear_link_state(message.chat.id)
    bot.reply_to(message, "Отменено.", reply_markup=main_keyboard())

@bot.message_handler(commands=["unlink"])
@bot.message_handler(func=lambda m: m.text in ("🚪 Отвязать", "Отвязать"))
def unlink_account(message):
    chat_id = message.chat.id
    db.clear_link_state(chat_id)
    from database import supabase_request
    supabase_request("telegram_users", method="PATCH", params={"telegram_chat_id": f"eq.{chat_id}"}, data={"telegram_chat_id": None})
    bot.reply_to(message, "✅ Telegram отвязан.", reply_markup=main_keyboard())

@bot.message_handler(func=lambda m: db.get_link_state(m.chat.id) is not None)
def handle_login_flow(message):
    chat_id = message.chat.id
    state = db.get_link_state(chat_id)
    text = (message.text or "").strip()

    if state["step"] == "support":
        if text in ("❌ Отмена", "Отмена", "/cancel"):
            db.clear_link_state(chat_id)
            bot.reply_to(message, "Отменено.", reply_markup=main_keyboard())
            return
        db.clear_link_state(chat_id)
        user = db.get_user_by_chat_id(chat_id)
        email = user['username'] if user else "не привязан"
        admin_text = f"💬 Support\nОт: {message.from_user.first_name} (@{message.from_user.username})\nEmail: {email}\n\n{text}"
        if ADMIN_CHAT_ID:
            bot.send_message(ADMIN_CHAT_ID, admin_text)
        bot.reply_to(message, "✅ Сообщение отправлено.", reply_markup=main_keyboard())
        return

    if state["step"] == "email":
        if "@" not in text:
            bot.reply_to(message, "❌ Неверный email.", reply_markup=cancel_keyboard())
            return
        db.set_link_state(chat_id, "password", text.lower())
        bot.reply_to(message, f"📧 Email: `{text}`\n\n🔐 Теперь введите пароль:", parse_mode="Markdown", reply_markup=cancel_keyboard())
        return

    if state["step"] == "password":
        email = state.get("email", "")
        db.clear_link_state(chat_id)
        bot.send_message(chat_id, "⏳ Проверяю...")

        res = verify_login_supabase(email, text)
        if res.get("error"):
            msg = "❌ Ошибка: Неверный email или пароль."
            bot.send_message(chat_id, msg, reply_markup=main_keyboard())
            return

        db.link_user_by_email(email, chat_id)
        user_data = res.get("user_data") or db.fetch_user_data_from_supabase(email) or {}
        bot.send_message(chat_id, f"✅ Аккаунт привязан!", reply_markup=main_keyboard())
        bot.send_message(chat_id, format_balance_message(email, user_data), reply_markup=main_keyboard())

# --- Новая функция для ответов администратора ---

@bot.message_handler(commands=["reply"])
def handle_admin_reply(message):
    if message.chat.id != int(ADMIN_CHAT_ID) and str(message.chat.id) != str(ADMIN_CHAT_ID):
        return

    text = message.text
    # Ожидаем формат: /reply session_id текст_ответа
    try:
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "❌ Формат: `/reply session_id текст`\nПример: `/reply abc-123 Здравствуйте!`", parse_mode="Markdown")
            return

        session_id = parts[1]
        reply_text = parts[2]

        db.save_support_message(session_id, 'admin', text=reply_text)
        bot.reply_to(message, f"✅ Ответ отправлен в сессию `{session_id}`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: True)
def handle_unknown(message):
    # Проверка на команду /reply в тексте, если вдруг handler не сработал
    if message.text and message.text.startswith("/reply"):
        handle_admin_reply(message)
        return

    if db.get_link_state(message.chat.id): return
    bot.reply_to(message, "Выберите действие на клавиатуре 👇", reply_markup=main_keyboard())

if __name__ == "__main__":
    print(f"🚀 Bot @{BOT_USERNAME} started in POLLING mode")
    bot.infinity_polling()
