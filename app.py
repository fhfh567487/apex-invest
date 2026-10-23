import os
  import json
  from flask import Flask, render_template, request, jsonify, session
  from flask_cors import CORS
  from dotenv import load_dotenv
  import requests

  load_dotenv()

  app = Flask(__name__)
  CORS(app)
  app.secret_key = os.getenv("SECRET_KEY", "apex_secret_key_123")

  # Конфигурация
  SUPABASE_URL = os.getenv("SUPABASE_URL")
  SUPABASE_KEY = os.getenv("SUPABASE_KEY")
  ADMIN_EMAIL = "binarpok@gmail.com"
  BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
  ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

  def supabase_api(table, method="GET", params=None, data=None):
      url = f"{SUPABASE_URL}/rest/v1/{table}"
      headers = {
          "apikey": SUPABASE_KEY,
          "Authorization": f"Bearer {SUPABASE_KEY}",
          "Content-Type": "application/json",
      }
      if method == "GET":
          query = ""
          if params:
              query = "&".join([f"{k}=eq.{v}" for k, v in params.items()])
          url += f"?{query}" if query else ""
          r = requests.get(url, headers=headers, timeout=10)
      elif method == "POST":
          r = requests.post(url, headers=headers, json=data, timeout=10)
      elif method == "PATCH":
          filter_str = "&".join([f"{k}=eq.{v}" for k, v in params.items()])
          url += f"?{filter_str}"
          r = requests.patch(url, headers=headers, json=data, timeout=10)

      return r.json() if r.status_code < 400 else None

  @app.route("/")
  def home():
      return render_template("index.html")

  @app.route("/admin")
  def admin_panel():
      return render_template("admin.html")

  @app.route("/api/auth/register", methods=["POST"])
  def register():
      data = request.get_json()
      email = data.get("email")
      password = data.get("password")
      res = supabase_api("tradepiramid", "POST", data={"username": email, "password": password, "user_data": "{}"})
      if res:
          return jsonify({"success": True, "message": "Account created!"})
      return jsonify({"success": False, "error": "Registration failed"}), 400

  @app.route("/api/auth/login", methods=["POST"])
  def login():
      data = request.get_json()
      email = data.get("email")
      password = data.get("password")
      user = supabase_api("tradepiramid", "GET", {"username": email})
      if user and len(user) > 0 and user[0].get("password") == password:
          session['user'] = email
          return jsonify({"success": True, "user": email})
      return jsonify({"success": False, "error": "Invalid email or password"}), 401

  @app.route("/api/auth/logout")
  def logout():
      session.pop('user', None)
      return jsonify({"//success": True})

  @app.route("/api/invest", methods=["POST"])
  def invest():
      data = request.get_json()
      email = session.get('user')
      if not email: return jsonify({"success": False, "error": "Unauthorized"}), 401
      return jsonify({"success": True, "message": "Investment successful!"})

  @app.route("/api/user/stats")
  def get_stats():
      email = session.get('user')
      if not email: return jsonify({"error": "Unauthorized"}), 401
      user_data = supabase_api("tradepiramid", "GET", {"username": email})
      if user_data:
          return jsonify(user_data[0].get("user_//data", {}))
      return jsonify({"error": "No data found"}), 404

  if __name__ == "__main__":
      port = int(os.environ.get("PORT", 3000))
      app.run(host="0.0.0.0", port=port)
