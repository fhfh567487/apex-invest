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

# Supabase (те же данные, что на сайте)
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
    return row  # (id, username) or None


def link_user_by_email(email, chat_id):
    """Привязать telegram_chat_id к email (username)."""
    email = email.strip().lower()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
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


def fetch_user_data_from_supabase(email):
    """Забрать user_data из Supabase по email."""
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
    """Сколько накапало за сегодня по активным депозитам."""
    if not user_data:
        return 0.0
    transactions = user_data.get("transactions") or []
    today_profit = 0.0
    now = datetime.now(timezone.utc)

    for tx in transactions:
        if tx.get("type") != "DEPOSIT":
            continue
        if tx.get("status") in ("Completed", "Paid") or tx.get("payoutProcessed"):
            continue
        plan = tx.get("plan") or "Novice"
        config = PLAN_CONFIGS.get(plan, {"daily_pct": 0.12})
        daily_pct = tx.get("dailyPct") or config["daily_pct"]
        amount = float(tx.get("amount") or 0)
        # За сегодня начисляется 1 день * daily
        today_profit += amount * daily_pct

    return today_profit


def format_balance_message(email, user_data):
    balance = float(user_data.get("balance") or 0)
    total_profit = float(user_data.get("totalProfit") or 0)
    total_invested = float(user_data.get("totalInvested") or 0)
    active = int(user_data.get("activeDeposits") or 0)
    today = calc_today_profit(user_data)

    name = ""
    if user_data.get("firstName") or user_data.get("lastName"):
        name = f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}".strip()

    header = f"👤 *{name}*\n" if name else ""
    header += f"📧 `{email}`\n\n"

    text = (
        header
        + f"💰 *Баланс:* `${balance:.2f}`\n"
        + f"📈 *Всего заработано:* `${total_profit:.2f}`\n"
        + f"📅 *За сегодня (ожидаемо):* `${today:.2f}`\n"
        + f"📦 *Вложено:* `${total_invested:.2f}`\n"
        + f"🟢 *Активных депозитов:* `{active}`"
    )
    return text


def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("💰 Баланс", "📈 Заработок")
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
        args = message.text.split(maxsplit=1)

        # /start <payload> — payload = base64(email) с сайта или auth_token
        if len(args) > 1:
            payload = args[1].strip()

            # 1) Пробуем auth_token (старая схема)
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username FROM users WHERE auth_token = ?", (payload,)
            )
            user = cursor.fetchone()
            if user:
                user_id, username = user
                cursor.execute(
                    "UPDATE users SET telegram_chat_id = ?, auth_token = NULL WHERE id = ?",
                    (chat_id, user_id),
                )
                conn.commit()
                conn.close()
                bot.reply_to(
                    message,
                    f"🎉 *Аккаунт привязан!*\n\nЗдравствуйте, *{username}*!\n\n"
                    "Нажмите «Баланс» или «Заработок».",
                    parse_mode="Markdown",
                    reply_markup=main_keyboard(),
                )
                return
            conn.close()

            # 2) Пробуем base64(email) с сайта
            email = None
            try:
                # добавляем padding если нужно
                pad = "=" * (-len(payload) % 4)
                decoded = base64.b64decode(payload + pad).decode("utf-8")
                if "@" in decoded:
                    email = decoded.strip().lower()
            except Exception:
                pass

            if not email and "@" in payload:
                email = payload.strip().lower()

            if email:
                link_user_by_email(email, chat_id)
                bot.reply_to(
                    message,
                    f"🎉 *Аккаунт Apex привязан!*\n\n"
                    f"Email: `{email}`\n\n"
                    "Нажмите «💰 Баланс» или «📈 Заработок».",
                    parse_mode="Markdown",
                    reply_markup=main_keyboard(),
                )
                return

        bot.reply_to(
            message,
            "👋 *Добро пожаловать в Apex Invest Bot!*\n\n"
            "Чтобы привязать аккаунт — нажмите кнопку *Telegram* в личном кабинете на сайте.\n\n"
            "После привязки доступны:\n"
            "• 💰 Баланс\n"
            "• 📈 Заработок",
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )

    @bot.message_handler(commands=["balance", "bal"])
    @bot.message_handler(func=lambda m: m.text in ("💰 Баланс", "Баланс"))
    def handle_balance(message):
        chat_id = message.chat.id
        user = get_user_by_chat_id(chat_id)
        if not user:
            bot.reply_to(
                message,
                "❌ Аккаунт не привязан.\nНажмите кнопку *Telegram* в личном кабинете на сайте.",
                parse_mode="Markdown",
            )
            return

        email = user[1]
        user_data = fetch_user_data_from_supabase(email)
        if user_data is None:
            bot.reply_to(
                message,
                "⚠️ Не удалось загрузить данные. Попробуйте позже или проверьте, что аккаунт есть на сайте.",
            )
            return

        text = format_balance_message(email, user_data)
        bot.reply_to(message, text, parse_mode="Markdown", reply_markup=main_keyboard())

    @bot.message_handler(commands=["earn", "profit", "today"])
    @bot.message_handler(func=lambda m: m.text in ("📈 Заработок", "Заработок"))
    def handle_earnings(message):
        chat_id = message.chat.id
        user = get_user_by_chat_id(chat_id)
        if not user:
            bot.reply_to(
                message,
                "❌ Аккаунт не привязан.\nНажмите кнопку *Telegram* в личном кабинете на сайте.",
                parse_mode="Markdown",
            )
            return

        email = user[1]
        user_data = fetch_user_data_from_supabase(email)
        if user_data is None:
            bot.reply_to(
                message,
                "⚠️ Не удалось загрузить данные. Попробуйте позже.",
            )
            return

        total_profit = float(user_data.get("totalProfit") or 0)
        today = calc_today_profit(user_data)
        balance = float(user_data.get("balance") or 0)

        text = (
            f"📈 *Заработок*\n\n"
            f"📅 *За сегодня:* `${today:.2f}`\n"
            f"💎 *Всего заработано:* `${total_profit:.2f}`\n"
            f"💰 *Текущий баланс:* `${balance:.2f}`"
        )
        bot.reply_to(message, text, parse_mode="Markdown", reply_markup=main_keyboard())

    def run_bot():
        print("🚀 Telegram bot polling started...")
        bot.infinity_polling(skip_pending=True)

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()


# --- Flask routes (как было) ---

@app.route("/")
def home():
    try:
        return render_template("index.html")
    except Exception:
        return "Apex Invest API", 200


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
