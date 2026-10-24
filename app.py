  import os
  import base64
  import requests
  from flask import Flask, render_template, request, jsonify

  app = Flask(__name__)

  # Переменные окружения для работы с Telegram (настраиваются на Render)
  TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
  ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

  # Хранилище диалогов и статусов чатов
  chat_messages_memory = {}
  chat_states = {}  # "ai" | "waiting_human" | "human"


  def send_telegram_notification(session_id, message_text, image_data=None):
      """Отправка уведомления администратору в Telegram."""
      if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
          print("Telegram variables are missing.")
          return

      # ОБНОВЛЕННЫЙ ТЕКСТ УВЕДОМЛЕНИЯ
      text = (
          f"🔔 *Вас вызвали!*\n\n"
          f"👤 *Пользователь:* `{session_id}`\n"
          f"💬 *Сообщение:* {message_text or '[Запрос помощи]'}"
      )

      # Если отправлен скриншот
      if image_data and image_data.startswith("data:image"):
          try:
              header, encoded = image_data.split(",", 1)
              file_bytes = base64.b64decode(encoded)
              url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
              files = {'photo': ('screenshot.png', file_bytes, 'image/png')}
              data = {
                  "chat_id": ADMIN_CHAT_ID,
                  "caption": text,
                  "parse_mode": "Markdown"
              }
              requests.post(url, data=data, files=files, timeout=10)
              return
          except Exception as e:
              print("Error sending photo to Telegram:", e)

      # Текстовое сообщение
      url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
      payload = {
          "chat_id": ADMIN_CHAT_ID,
          "text": text,
          "parse_mode": "Markdown"
      }
      try:
          requests.post(url, json=payload, timeout=5)
      except Exception as e:
          print("Error sending message to Telegram:", e)


  @app.route('/')
  def index():
      return render_template('index.html')


  @app.route('/api/chat/get', methods=['GET'])
  @app.route('/get', methods=['GET'])
  def get_chat_messages():
      session_id = request.args.get('session_id')
      if not session_id:
          return jsonify({"status": "error", "message": "Missing session_id"}), 400

      messages = chat_messages_memory.get(session_id, [])
      state = chat_states.get(session_id, {"status": "ai"})

      return jsonify({
          "status": "success",
          "messages": messages,
          "chat_status": state.get("status", "ai")
      }), 200


  @app.route('/api/chat/send', methods=['POST'])
  @app.route('/send_message', methods=['POST'])
  def send_chat_message():
      data = request.get_json() or {}
      session_id = data.get('session_id')
      message_text = data.get('message', '').strip()
      image_data = data.get('image', None)
      action = data.get('action', None)  # 'solved_yes' или 'call_human'

      if not session_id:
          return jsonify({"status": "error", "message": "Missing session_id"}), 400

      if session_id not in chat_messages_memory:
          chat_messages_memory[session_id] = []
          chat_states[session_id] = {"status": "ai"}

      current_state = chat_states[session_id]

      # 1. Если пользователь подтвердил решение ("Да")
      if action == 'solved_yes':
          chat_messages_memory[session_id].append({
              "sender": "user",
              "text": "Да, проблема решена"
          })
          chat_messages_memory[session_id].append({
              "sender": "support",
              "text": "Приятного дня! Рады были помочь. Если возникнут новые вопросы — обращайтесь!"
          })
          chat_states[session_id]["status"] = "ai"
          return jsonify({"status": "success", "messages": chat_messages_memory[session_id]}), 200

      # 2. Если пользователь нажал "Позвать человека"
      if action == 'call_human':
          chat_messages_memory[session_id].append({
              "sender": "user",
              "text": "Позвать человека"
          })
          chat_messages_memory[session_id].append({
              "sender": "support",
              "text": "Оператор вызван. Пожалуйста, подождите, представитель поддержки подключится в ближайшее время."
          })
          chat_states[session_id]["status"] = "waiting_human"

          # Получаем последнее содержательное сообщение пользователя
          last_user_msg = "Запрос оператора через кнопку"
          for m in reversed(chat_messages_memory[session_id]):
              if m.get("sender") == "user" and m.get("text") != "Позвать человека":
                  last_user_msg = m.get("text") or "[Скриншот]"
                  break

          send_telegram_notification(session_id, last_user_msg, image_data)
          return jsonify({"status": "success", "messages": chat_messages_memory[session_id]}), 200

      # 3. Сообщение пользователя
      chat_messages_memory[session_id].append({
          "sender": "user",
          "text": message_text,
          "image": image_data
      })

      # Если диалог передан человеку, ИИ не отвечает
      if current_state["status"] in ["human", "waiting_human"]:
          return jsonify({"status": "success", "messages": chat_messages_memory[session_id]}), 200

      # 4. Логика ответа ИИ
      text_lower = message_text.lower()
      if any(word in text_lower for word in ["вывести", "вывод", "деньги", "снять"]):
          ai_reply = (
              "💰 **Как вывести средства:**\n"
              "1. Перейдите в раздел Dashboard.\n"
              "2. Убедитесь, что ваш KYC (верификация) успешно пройден.\n"
              "3. Нажмите «Request Withdrawal», выберите платежную систему, укажите реквизиты и сумму (от $10).\n\n"
              "Ваша проблема решена?"
          )
      elif any(word in text_lower for word in ["пополнить", "депозит", "инвестировать", "внести"]):
          ai_reply = (
              "🚀 **Как открыть инвестиционный депозит:**\n"
              "1. Выберите подходящий тарифный план (Novice, Pro, Master).\n"
              "2. Укажите сумму и удобную криптовалюту или карту.\n"
              "3. Переведите средства по указанным реквизитам.\n\n"
              "Ваша проблема решена?"
          )
      else:
          ai_reply = "Я виртуальный помощник Apex Invest. Чем я могу вам помочь?\n\nВаша проблема решена?"

      # Ответ ИИ с флагом на показ кнопок "Да" / "Позвать человека"
      chat_messages_memory[session_id].append({
          "sender": "support",
          "text": ai_reply,
          "show_buttons": True
      })

      return jsonify({
          "status": "success",
          "messages": chat_messages_memory[session_id]
      }), 200


  if __name__ == '__main__':
      app.run(host='0.0.0.0', port=5000, debug=True)
