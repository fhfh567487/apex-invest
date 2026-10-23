import os
  import threading
  from flask import Flask, render_template, request, jsonify
  from flask_cors import CORS
  from dotenv import load_dotenv
  import database as db
  import requests
  import bot_worker  # Импортируем логику бота

  load_dotenv()

  app = Flask(__name__)
  CORS(app)
  app.secret_key = os.getenv("SECRET_KEY", "apex_secret_key_123")

  BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
  ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
  BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "Appexinvestet_bot")

  @app.route("/")
  def home():
      try:
          return render_template("index.html")
      except Exception:
          return "Apex Invest API", 200

  @app.route("/api/bot-status")
  def bot_status():
      return jsonify({
          "bot_initialized": bool(BOT_TOKEN),
          "bot_username": BOT_USERNAME,
          "token_set": bool(BOT_TOKEN),
          "admin_chat_id_set": ADMIN_CHAT_ID is not None,
          "admin_chat_id": ADMIN_CHAT_ID,
      })

  def notify_admin_telegram(session_id, message, has_image=False):
      if not BOT_TOKEN or not ADMIN_CHAT_ID:
          return False, "Config missing"

      preview = (message or "").strip() or ("(фото)" if has_image else "(пусто)")
      text = f"💬 Support (сайт)\n\nsession: {session_id}\n\n{preview[:800]}"

      url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
      try:
          r = requests.post(url, json={"chat_id": ADMIN_CHAT_ID, "text": text}, timeout=15)
          return r.ok, r.text if not r.ok else None
      except Exception as e:
          return False, str(e)

  @app.route("/api/chat/send", methods=["POST", "OPTIONS"])
  def chat_send():
      if request.method == "OPTIONS": return ("", 204)
      data = request.get_json(silent=True) or {}
      session_id = (data.get("session_id") or "").strip()
      message = (data.get("message") or "").strip()
      image = data.get("image")

      if not session_id or (not message and not image):
          return jsonify({"success": False, "error": "invalid data"}), 400

      db.save_support_message(session_id, 'user', text=message, image=image)
      tg_ok, tg_err = notify_admin_telegram(session_id, message, bool(image))
      return jsonify({"success": True, "telegram_notified": tg_ok})

  @app.route("/api/chat/get", methods=["GET", "OPTIONS"])
  def chat_get():
      if request.method == "OPTIONS": return ("", 204)
      session_id = (request.args.get("session_id") or "").strip()
      if not session_id: return jsonify({"messages": []})
      messages = db.get_support_history(session_id) or []
      return jsonify({"messages": messages})

  @app.route("/api/chat/reply", methods=["POST"])
  def chat_reply():
      data = request.get_json(silent=True) or {}
      session_id = (data.get("session_id") or "").strip()
      message = (data.get("message") or "").strip()
      secret = data.get("secret") or request.headers.get("X-Admin-Secret")

      if secret != os.getenv("ADMIN_SECRET", "apex_admin"):
          return jsonify({"success": False, "error": "forbidden"}), 403

      db.save_support_message(session_id, 'admin', text=message)
      return jsonify({"success": True})

  @app.route("/api/telegram/connect", methods=["POST"])
  def connect_telegram():
      data = request.json or {}
      email = (data.get("email") or "").strip().lower()
      import secrets
      auth_token = secrets.token_hex(8)

      # Сохраняем токен в Supabase
      db.supabase_request("telegram_users", method="POST", data={"username": email, "auth_token": auth_token})

      deep_link = f"https://t.me/{BOT_USERNAME}?start={auth_token}"
      return jsonify({"success": True, "link": deep_link})

  @app.route("/api/notify", methods=["POST"])
  def notify_user():
      data = request.json or {}
      user_id = data.get("user_id")
      text = data.get("message")
      if not user_id or not text:
          return jsonify({"success": False, "error": "missing data"}), 400
      user = db.get_user_by_chat_id(user_id)
      if not user or not user.get("telegram_chat_id"):
          return jsonify({"success": False, "error": "Telegram not linked"}), 404
      url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
      try:
          r = requests.post(url, json={"chat_id": user["telegram_chat_id"], "text": text}, timeout=15)
          return jsonify({"success": r.ok})
      except Exception:
          return jsonify({"success": False}), 500

  # --- ЗАПУСК БОТА В ОТДЕЛЬНОМ ПОТОКЕ ---
  def run_bot():
      print("🚀 Starting Telegram Bot thread...")
      try:
          # Вызываем функцию запуска из bot_worker.py
          # В bot_worker.py функция должна называться run_bot_polling или аналогично
          # Для этого в bot_worker.py в конце мы используем bot.infinity_polling()
          import bot_worker
          # Поскольку в bot_worker.py код запуска в if __name__ == "__main__",
          # нам нужно вызвать функцию запуска вручную.
          # Мы добавим в bot_worker.py функцию start_bot() для этого.
          if hasattr(bot_worker, 'bot'):
              bot_worker.bot.infinity_polling()
      except Exception as e:
          print(f"❌ Bot thread error: {e}")

  if __name__ == "__main__":
      # Запускаем бота в фоновом режиме
      bot_thread = threading.Thread(target=run_bot, daemon=True)
      bot_thread.start()

      port = int(os.environ.get("PORT", 3000))
      app.run(host="0.0.0.0", port=port)
