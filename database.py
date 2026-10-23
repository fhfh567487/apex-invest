import os
  import json
  import requests
  from dotenv import load_dotenv

  load_dotenv()

  SUPABASE_URL = os.getenv("SUPABASE_URL")
  SUPABASE_KEY = os.getenv("SUPABASE_KEY")

  headers = {
      "apikey": SUPABASE_KEY,
      "Authorization": f"Bearer {SUPABASE_KEY}",
      "Content-Type": "application/json",
  }

  def supabase_request(table, method="GET", params=None, data=None):
      url = f"{SUPABASE_URL}/rest/v1/{table}"
      try:
          if method == "GET":
              r = requests.get(url, headers=headers, params=params, timeout=15)
          elif method == "POST":
              r = requests.post(url, headers=headers, json=data, timeout=15)
          elif method == "PATCH":
              r = requests.patch(url, headers=headers, json=data, timeout=15)
          elif method == "DELETE":
              r = requests.delete(url, headers=headers, params=params, timeout=15)

          if r.status_code >= 400:
              print(f"Supabase Error {r.status_code}: {r.text}")
              return None
          return r.json()
      except Exception as e:
          print(f"Supabase Request Exception: {e}")
          return None

  def get_user_by_chat_id(chat_id):
      res = supabase_request("telegram_users", params={"telegram_chat_id": f"eq.{chat_id}", "select": "username"})
      return res[0] if res else None

  def get_user_by_auth_token(token):
      res = supabase_request("telegram_users", params={"auth_token": f"eq.{token}", "select": "username"})
      return res[0] if res else None

  def link_user_by_email(email, chat_id):
      email = email.strip().lower()
      supabase_request("telegram_users", method="PATCH",
                       params={"telegram_chat_id": f"eq.{chat_id}"},
                       data={"telegram_chat_id": None})

      user_data = supabase_request("tradepiramid", params={"username": f"eq.{email}", "select": "username"})

      if user_data:
          username = user_data[0]['username']
          existing = supabase_request("telegram_users", params={"username": f"eq.{username}"})
          if existing:
              supabase_request("telegram_users", method="PATCH",
                               params={"username": f"eq.{username}"},
                               data={"telegram_chat_id": chat_id, "auth_token": None})
          else:
              supabase_request("telegram_users", method="POST",
                               data={"username": username, "telegram_chat_id": chat_id})
      return email

  def get_link_state(chat_id):
      res = supabase_request("link_states", params={"chat_id": f"eq.{chat_id}", "select": "*"})
      return res[0] if res else None

  def set_link_state(chat_id, step, email=None):
      existing = get_link_state(chat_id)
      if existing:
          supabase_request("link_states", method="PATCH",
                           params={"chat_id": f"eq.{chat_id}"},
                           data={"step": step, "email": email})
      else:
          supabase_request("link_states", method="POST",
                           data={"chat_id": chat_id, "step": step, "email": email})

  def clear_link_state(chat_id):
      supabase_request("link_states", method="DELETE", params={"chat_id": f"eq.{chat_id}"})

  def save_support_message(session_id, sender, text=None, image=None):
      return supabase_request("support_messages", method="POST",
                               data={"session_id": session_id, "sender": sender, "text": text, "image": image})

  def get_support_history(session_id):
      return supabase_request("support_messages", params={"session_id": f"eq.{session_id}", "select": "*", "order": "id.asc"})

  def fetch_user_data_from_supabase(email):
      res = supabase_request("tradepiramid", params={"username": f"eq.{email}", "select": "user_data"})
      if not res: return None
      raw = res[0].get("user_data")
      if isinstance(raw, str):
          try: return json.loads(raw)
          except: return {}
      return raw or {}
