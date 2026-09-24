import os
import sqlite3
import threading
import secrets
import json
import base64
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify
import telebot
from telebot import types
from dotenv import load_dotenv
import requests

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "Appexinvestet_bot")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://bycfzzqpnnsqgwtzccdc.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_sYHXSnwWJgT178wtP8MISA_t7A030f2")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "apex_secret_key_123")

DB_NAME = "database.db"

PLAN_CONFIGS = {
    "Novice": {"days": 1, "daily_pct": 0.12},
    "Pro": {"days": 10, "daily_pct": 0.25},
    "Master": {"days": 30, "daily_pct": 0.15},
}

# Состояния диалога: chat_id -> {"step": "email"|"password", "email": "..."}
user_states = {}


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            telegram_chat_id INTEGER,
            auth_token TEXT
        )
    """)
    # Миграция: добавить колонки, если таблица была старой
    cursor.execute("PRAGMA table_info(users)")
    cols = {row[1] for row in cursor.fetchall()}
    if "telegram_chat_id" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN telegram_chat_id INTEGER")
        print("DB migration: added telegram_chat_id")
    if "auth_token" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN auth_token TEXT")
        print("DB migration: added auth_token")
    if "username" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
        print("DB migration: added username")
    conn.commit()
    conn.close()


init_db()


def get_user_by_chat_id(chat_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username FROM users WHERE telegram_chat_id = ?", (chat_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row


def get_user_by_auth_token(token):
    """Найти пользователя по одноразовому auth_token со сайта."""
    if not token:
        return None
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username FROM users WHERE auth_token = ?", (token,)
    )
    row = cursor.fetchone()
    conn.close()
    return row


def link_user_by_email(email, chat_id):
    email = email.strip().lower()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Сначала отвяжем этот chat_id от других аккаунтов
    cursor.execute(
        "UPDATE users SET telegram_chat_id = NULL WHERE telegram_chat_id = ?",
        (chat_id,),
    )
    cursor.execute("SELECT id FROM users WHERE username = ?", (email,))
    row = cursor.fetchone()
    if row:
        cursor.execute(
            "UPDATE users SET telegram_chat_id = ?, auth_token = NULL WHERE id = ?",
            (chat_id, row[0]),
        )
    else:
        cursor.execute(
            "INSERT INTO users (username, telegram_chat_id) VALUES (?, ?)",
            (email, chat_id),
        )
    conn.commit()
    conn.close()
    return email


def send_already_linked(chat_id, email):
    """Приветствие, если Telegram уже привязан — без повторного ввода пароля."""
    user_data = fetch_user_data_from_supabase(email) or {}
    bot.send_message(
        chat_id,
        f"👋 Снова здравствуйте!\n\nАккаунт: `{email}`\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )
    bot.send_message(
        chat_id,
        format_balance_message(email, user_data),
        reply_markup=main_keyboard(),
    )


def verify_login_supabase(email, password):
    """Проверка email + пароль в Supabase (таблица tradepiramid)."""
    try:
        email = email.strip().lower()
        password = password.strip()
        url = f"{SUPABASE_URL}/rest/v1/tradepiramid"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        # Берём пользователя по email, пароль сравниваем сами
        # (фильтр password=eq. может блокироваться RLS)
        params = {
            "username": f"eq.{email}",
            "select": "username,password,user_data",
        }
        r = requests.get(url, headers=headers, params=params, timeout=15)
        print(f"Supabase login status={r.status_code} body={r.text[:300]}")
        if r.status_code != 200:
            return {"error": f"db_{r.status_code}"}
        data = r.json()
        if not data:
            return {"error": "not_found"}
        row = data[0]
        db_pass = str(row.get("password") or "")
        if db_pass != password:
            return {"error": "bad_password"}
        return {"ok": True, "username": row.get("username"), "user_data": row.get("user_data")}
    except Exception as e:
        print(f"Supabase login error: {e}")
        return {"error": "exception"}


def fetch_user_data_from_supabase(email):
    try:
        url = f"{SUPABASE_URL}/rest/v1/tradepiramid"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        params = {"username": f"eq.{email}", "select": "user_data"}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data:
            return None
        raw = data[0].get("user_data")
        if isinstance(raw, str):
            return json.loads(raw)
        return raw or {}
    except Exception as e:
        print(f"Supabase error: {e}")
        return None


def calc_today_profit(user_data):
    if not user_data:
        return 0.0
    transactions = user_data.get("transactions") or []
    today_profit = 0.0
    for tx in transactions:
        if tx.get("type") != "DEPOSIT":
            continue
        if tx.get("status") in ("Completed", "Paid") or tx.get("payoutProcessed"):
            continue
        plan = tx.get("plan") or "Novice"
        config = PLAN_CONFIGS.get(plan, {"daily_pct": 0.12})
        daily_pct = tx.get("dailyPct") or config["daily_pct"]
        amount = float(tx.get("amount") or 0)
        today_profit += amount * daily_pct
    return today_profit


def format_balance_message(email, user_data):
    if not isinstance(user_data, dict):
        user_data = {}
    balance = float(user_data.get("balance") or 0)
    total_profit = float(user_data.get("totalProfit") or 0)
    total_invested = float(user_data.get("totalInvested") or 0)
    active = int(user_data.get("activeDeposits") or 0)
    today = calc_today_profit(user_data)

    name = ""
    if user_data.get("firstName") or user_data.get("lastName"):
        name = f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}".strip()

    lines = []
    if name:
        lines.append(f"👤 {name}")
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
    return kb


def cancel_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("❌ Отмена")
    return kb


bot = None
if BOT_TOKEN:
    try:
        bot = telebot.TeleBot(BOT_TOKEN)
        print("✅ Telegram bot initialized")
    except Exception as e:
        print(f"❌ Error initializing bot: {e}")

if bot:

    @bot.message_handler(commands=["start"])
    def handle_start(message):
        chat_id = message.chat.id
        user_states.pop(chat_id, None)

        # Уже привязан — никогда не просим email/пароль повторно
        linked = get_user_by_chat_id(chat_id)
        if linked:
            send_already_linked(chat_id, linked[1])
            return

        args = message.text.split(maxsplit=1)
        payload = args[1].strip() if len(args) > 1 else ""

        if payload:
            payload_lower = payload.lower()

            # 1) Одноразовый auth_token со сайта (/api/telegram/connect)
            token_user = get_user_by_auth_token(payload)
            if token_user:
                email = token_user[1]
                link_user_by_email(email, chat_id)
                user_data = fetch_user_data_from_supabase(email) or {}
                bot.send_message(
                    chat_id,
                    f"✅ Аккаунт успешно привязан!\n\nEmail: `{email}`\n\n"
                    "Теперь доступны баланс и заработок.",
                    parse_mode="Markdown",
                    reply_markup=main_keyboard(),
                )
                bot.send_message(
                    chat_id,
                    format_balance_message(email, user_data),
                    reply_markup=main_keyboard(),
                )
                return

            # 2) С сайта: ?start=link — просим email только если ещё не привязан
            if payload_lower == "link":
                user_states[chat_id] = {"step": "email"}
                bot.reply_to(
                    message,
                    "📧 Введите *email* от аккаунта на сайте Apex Invest:",
                    parse_mode="Markdown",
                    reply_markup=cancel_keyboard(),
                )
                return

            # 3) hex(email) — сайт передаёт email залогиненного пользователя
            email = None
            try:
                if all(c in "0123456789abcdef" for c in payload_lower) and len(payload_lower) % 2 == 0:
                    decoded = bytes.fromhex(payload_lower).decode("utf-8")
                    if "@" in decoded:
                        email = decoded.strip().lower()
            except Exception:
                pass
            if email:
                # Уже привязан к этому же email с другого chat? всё равно спросим пароль
                # только если этот chat ещё не привязан (мы уже вышли выше, если был).
                user_states[chat_id] = {"step": "password", "email": email}
                bot.reply_to(
                    message,
                    f"👋 Email: `{email}`\n\n"
                    "Введите *пароль* от аккаунта на сайте, чтобы привязать Telegram:",
                    parse_mode="Markdown",
                    reply_markup=cancel_keyboard(),
                )
                return

        # Нет payload и не привязан
        bot.reply_to(
            message,
            "👋 *Добро пожаловать в Apex Invest Bot!*\n\n"
            "Чтобы смотреть баланс и заработок — привяжите аккаунт.\n\n"
            "Нажмите *«🔗 Привязать аккаунт»* и введите email и пароль с сайта.",
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )

    @bot.message_handler(commands=["link", "login"])
    @bot.message_handler(func=lambda m: m.text in ("🔗 Привязать аккаунт", "Привязать аккаунт"))
    def start_link(message):
        chat_id = message.chat.id
        user_states[chat_id] = {"step": "email"}
        bot.reply_to(
            message,
            "📧 Введите *email* от аккаунта на сайте Apex Invest:",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard(),
        )

    @bot.message_handler(func=lambda m: m.text in ("❌ Отмена", "Отмена"))
    def cancel_link(message):
        chat_id = message.chat.id
        user_states.pop(chat_id, None)
        bot.reply_to(
            message,
            "Отменено.",
            reply_markup=main_keyboard(),
        )

    @bot.message_handler(commands=["unlink"])
    @bot.message_handler(func=lambda m: m.text in ("🚪 Отвязать", "Отвязать"))
    def unlink_account(message):
        chat_id = message.chat.id
        user_states.pop(chat_id, None)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET telegram_chat_id = NULL WHERE telegram_chat_id = ?",
            (chat_id,),
        )
        conn.commit()
        conn.close()
        bot.reply_to(
            message,
            "✅ Telegram отвязан от аккаунта.\nЧтобы снова привязать — нажмите «🔗 Привязать аккаунт».",
            reply_markup=main_keyboard(),
        )

    @bot.message_handler(commands=["balance", "bal"])
    @bot.message_handler(func=lambda m: m.text in ("💰 Баланс", "Баланс"))
    def handle_balance(message):
        chat_id = message.chat.id
        if chat_id in user_states:
            return  # идёт процесс входа — не перехватываем

        user = get_user_by_chat_id(chat_id)
        if not user:
            bot.reply_to(
                message,
                "❌ Аккаунт не привязан.\nНажмите *«🔗 Привязать аккаунт»* и введите email + пароль.",
                parse_mode="Markdown",
                reply_markup=main_keyboard(),
            )
            return

        email = user[1]
        user_data = fetch_user_data_from_supabase(email)
        if user_data is None:
            bot.reply_to(
                message,
                "⚠️ Не удалось загрузить данные. Попробуйте позже.",
                reply_markup=main_keyboard(),
            )
            return

        text = format_balance_message(email, user_data)
        bot.reply_to(message, text, reply_markup=main_keyboard())

    @bot.message_handler(commands=["earn", "profit", "today"])
    @bot.message_handler(func=lambda m: m.text in ("📈 Заработок", "Заработок"))
    def handle_earnings(message):
        chat_id = message.chat.id
        if chat_id in user_states:
            return

        user = get_user_by_chat_id(chat_id)
        if not user:
            bot.reply_to(
                message,
                "❌ Аккаунт не привязан.\nНажмите *«🔗 Привязать аккаунт»*.",
                parse_mode="Markdown",
                reply_markup=main_keyboard(),
            )
            return

        email = user[1]
        user_data = fetch_user_data_from_supabase(email)
        if user_data is None:
            bot.reply_to(message, "⚠️ Не удалось загрузить данные.", reply_markup=main_keyboard())
            return

        total_profit = float(user_data.get("totalProfit") or 0)
        today = calc_today_profit(user_data)
        balance = float(user_data.get("balance") or 0)

        text = (
            f"📈 Заработок\n\n"
            f"📅 За сегодня: ${today:.2f}\n"
            f"💎 Всего заработано: ${total_profit:.2f}\n"
            f"💰 Текущий баланс: ${balance:.2f}"
        )
        bot.reply_to(message, text, reply_markup=main_keyboard())

    @bot.message_handler(func=lambda m: m.chat.id in user_states)
    def handle_login_flow(message):
        chat_id = message.chat.id
        state = user_states.get(chat_id)
        if not state:
            return

        text = (message.text or "").strip()

        if state["step"] == "email":
            if "@" not in text or "." not in text:
                bot.reply_to(
                    message,
                    "❌ Некорректный email. Введите ещё раз (пример: name@mail.com):",
                    reply_markup=cancel_keyboard(),
                )
                return
            state["email"] = text.lower()
            state["step"] = "password"
            bot.reply_to(
                message,
                f"📧 Email: `{state['email']}`\n\n"
                "🔐 Теперь введите *пароль* от аккаунта на сайте:",
                parse_mode="Markdown",
                reply_markup=cancel_keyboard(),
            )
            return

        if state["step"] == "password":
            email = state.get("email", "")
            password = text
            user_states.pop(chat_id, None)

            try:
                bot.send_message(chat_id, "⏳ Проверяю данные...")
            except Exception as e:
                print("send check msg error:", e)

            try:
                account = verify_login_supabase(email, password)
                print("login result:", account)

                if not account or account.get("error"):
                    err = (account or {}).get("error", "unknown")
                    if err == "not_found":
                        msg = "❌ Аккаунт с таким email не найден на сайте."
                    elif err == "bad_password":
                        msg = "❌ Неверный пароль. Нажмите «🔗 Привязать аккаунт» и попробуйте снова."
                    else:
                        msg = "❌ Ошибка проверки базы. Попробуйте позже."
                    bot.send_message(chat_id, msg, reply_markup=main_keyboard())
                    return

                link_user_by_email(email, chat_id)

                user_data = account.get("user_data")
                if isinstance(user_data, str):
                    try:
                        user_data = json.loads(user_data)
                    except Exception:
                        user_data = {}
                if not isinstance(user_data, dict):
                    user_data = fetch_user_data_from_supabase(email) or {}

                bot.send_message(
                    chat_id,
                    f"✅ Аккаунт успешно привязан!\n\nEmail: {email}\n\nТеперь доступны баланс и заработок.",
                    reply_markup=main_keyboard(),
                )
                bot.send_message(
                    chat_id,
                    format_balance_message(email, user_data),
                    reply_markup=main_keyboard(),
                )
            except Exception as e:
                print("password step EXCEPTION:", type(e), e)
                try:
                    bot.send_message(
                        chat_id,
                        f"❌ Ошибка: {type(e).__name__}: {e}",
                        reply_markup=main_keyboard(),
                    )
                except Exception:
                    pass
            return


    def run_bot():
        """Надёжный polling: снимаем webhook, перезапускаем при ошибках."""
        import time

        # Снимаем webhook — иначе getUpdates молчит
        try:
            bot.delete_webhook(drop_pending_updates=False)
            print("✅ Webhook cleared, switching to polling")
        except Exception as e:
            print(f"⚠️ delete_webhook: {e}")

        while True:
            try:
                print("🚀 Telegram bot polling started...")
                # long_polling_timeout — реже обрывы на PaaS
                bot.infinity_polling(
                    skip_pending=False,  # обработаем висящие /start
                    timeout=20,
                    long_polling_timeout=20,
                    allowed_updates=["message"],
                )
            except Exception as e:
                print(f"❌ Bot polling error: {type(e).__name__}: {e}")
                print("⏳ Restart polling in 5 sec...")
                time.sleep(5)

    # Запускаем только в одном процессе (gunicorn worker 0 или локально)
    # GUNICORN_WORKER_ID / RUN_BOT: на части хостов worker id нет — тогда стартуем всегда,
    # но Procfile должен быть с -w 1, иначе Conflict getUpdates.
    _should_run_bot = os.environ.get("RUN_BOT", "1") != "0"
    if _should_run_bot:
        bot_thread = threading.Thread(target=run_bot, daemon=True, name="tg-bot-polling")
        bot_thread.start()
        print("✅ Bot polling thread started")


@app.route("/")
def home():
    try:
        return render_template("index.html")
    except Exception:
        return "Apex Invest API", 200


@app.route("/api/bot-status")
def bot_status():
    """Проверка: жив ли бот и есть ли токен."""
    ok = bot is not None and bool(BOT_TOKEN)
    return jsonify({
        "bot_initialized": ok,
        "bot_username": BOT_USERNAME,
        "token_set": bool(BOT_TOKEN),
        "hint": "Если бот не отвечает — в Procfile нужен 1 worker и переменная TELEGRAM_BOT_TOKEN",
    })


@app.route("/api/telegram/connect", methods=["POST"])
def connect_telegram():
    data = request.json or {}
    user_id = data.get("user_id", 1)
    email = (data.get("email") or "").strip().lower()

    auth_token = secrets.token_hex(8)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if email:
        cursor.execute("SELECT id FROM users WHERE username = ?", (email,))
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE users SET auth_token = ? WHERE id = ?", (auth_token, row[0])
            )
        else:
            cursor.execute(
                "INSERT INTO users (username, auth_token) VALUES (?, ?)",
                (email, auth_token),
            )
    else:
        cursor.execute(
            "UPDATE users SET auth_token = ? WHERE id = ?", (auth_token, user_id)
        )

    conn.commit()
    conn.close()

    deep_link = f"https://t.me/{BOT_USERNAME}?start={auth_token}"
    return jsonify({"success": True, "link": deep_link})


@app.route("/api/notify", methods=["POST"])
def notify_user():
    data = request.json or {}
    user_id = data.get("user_id")
    text = data.get("message")

    if not user_id or not text:
        return jsonify({"success": False, "error": "user_id and message are required"}), 400

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_chat_id FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        return jsonify({"success": False, "error": "Telegram not linked"}), 404

    if bot:
        try:
            bot.send_message(row[0], text, parse_mode="Markdown")
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": False, "error": "Bot is not active"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
