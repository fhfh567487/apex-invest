import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)  # Включаем CORS для обработки запросов с GitHub Pages

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    return render_template('index.html')

# 1. Инициализация чата
@app.route('/api/support/init', methods=['POST'])
def init_chat():
    data = request.json or {}
    email = data.get('email', 'guest@apexinvest.com')

    res = supabase.table('support_chats').select('*').eq('user_email', email).neq('status', 'closed').execute()

    if res.data:
        chat = res.data[0]
    else:
        chat_res = supabase.table('support_chats').insert({'user_email': email, 'status': 'bot'}).execute()
        chat = chat_res.data[0]

        supabase.table('support_messages').insert({
            'chat_id': chat['id'],
            'sender_type': 'bot',
            'message': 'Hello! I am the Apex Invest AI Assistant. How can I help you today?'
        }).execute()

    return jsonify({'success': True, 'chat': chat})

# Добавляем недостающий эндпоинт для получения сообщений (исправление ошибки 500)
@app.route('/api/chat/get', methods=['GET'])
@app.route('/api/support/get', methods=['GET'])
def get_messages():
    session_id = request.args.get('session_id') or request.args.get('session')
    if not session_id:
        return jsonify({'success': False, 'error': 'Session ID is required'}), 400

    # Надежный поиск чата: сначала по ID, потом по Email
    chat = None

    # 1. Пробуем найти по ID
    try:
        res_id = supabase.table('support_chats').select('id').eq('id', session_id).execute()
        if res_id.data:
            chat = res_id.data[0]
    except:
        pass

    # 2. Если не нашли по ID, пробуем по email
    if not chat:
        try:
            res_email = supabase.table('support_chats').select('id').eq('user_email', session_id).execute()
            if res_email.data:
                chat = res_email.data[0]
        except:
            pass

    if not chat:
        return jsonify({'success': False, 'error': 'Chat not found'}), 404

    chat_id = chat['id']

    # Получаем все сообщения этого чата, отсортированные по времени
    messages_res = supabase.table('support_messages').select('*').eq('chat_id', chat_id).order('created_at').execute()

    return jsonify({'success': True, 'messages': messages_res.data})

# 2. Вызов специалиста
@app.route('/api/support/call-agent', methods=['POST'])
def call_agent():
    data = request.json or {}
    chat_id = data.get('chat_id')
    
    supabase.table('support_chats').update({'status': 'waiting_for_agent'}).eq('id', chat_id).execute()
    
    msg_res = supabase.table('support_messages').insert({
        'chat_id': chat_id,
        'sender_type': 'bot',
        'message': 'A specialist has been notified. Please wait for an agent to connect...'
    }).execute()
    
    return jsonify({'success': True, 'message': msg_res.data[0]})

# 3. Отправка сообщений
@app.route('/api/chat/send', methods=['POST'])
@app.route('/api/support/send', methods=['POST'])
def send_message():
    try:
        data = request.json or {}
        chat_id = data.get('chat_id')
        text = data.get('message', '').strip()

        if not chat_id:
            return jsonify({'success': False, 'error': 'chat_id is missing'}), 400

        # Сохраняем сообщение пользователя
        supabase.table('support_messages').insert({
            'chat_id': chat_id,
            'sender_type': 'user',
            'message': text
        }).execute()

        chat_res = supabase.table('support_chats').select('status').eq('id', chat_id).execute()
        status = chat_res.data[0]['status'] if chat_res.data else 'bot'

        if status == 'bot':
            text_lower = text.lower()
            # Логика обработки ответов "да/нет"
            if text_lower in ['да', 'yes', 'решена', 'solved']:
                ai_reply = "Отлично! Рад был помочь. Хорошего дня!"
                supabase.table('support_chats').update({'status': 'closed'}).eq('id', chat_id).execute()
            elif text_lower in ['нет', 'no', 'не решена', 'not solved']:
                ai_reply = "Мне жаль, что я не смог помочь. Хотите позвать специалиста для решения вашего вопроса?"
            else:
                ai_reply = f"Спасибо за ваше сообщение: '{text}'. Я постарался найти ответ, но если вам нужна детальная консультация, пожалуйста, напишите 'Нет', если ваша проблема не решена, или нажмите 'Позвать специалиста'.\n\nВаша проблема решена?"

            # Сохраняем ответ бота
            bot_msg_res = supabase.table('support_messages').insert({
                'chat_id': chat_id,
                'sender_type': 'bot',
                'message': ai_reply
            }).execute()

            bot_msg = bot_msg_res.data[0] if bot_msg_res.data else {'message': ai_reply}

            # Возвращаем ответ в обоих форматах для совместимости с разными версиями фронтенда
            return jsonify({
                'success': True,
                'bot_reply': bot_msg,
                'message': bot_msg['message'],
                'status': status
            })

        return jsonify({'success': True, 'status': status})
    except Exception as e:
        print(f"Error in send_message: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# 4. Панель Администратора: Список ожидающих чатов
@app.route('/api/admin/pending_chats', methods=['GET'])
def get_pending_chats():
    # Получаем все чаты со статусом 'waiting_for_agent'
    res = supabase.table('support_chats').select('*, support_messages(message, sender_type)').eq('status', 'waiting_for_agent').execute()

    pending_chats = []
    for chat in res.data:
        # Берем последнее сообщение пользователя для предпросмотра
        messages = chat.get('support_messages', [])
        last_msg = next((m['message'] for m in reversed(messages) if m['sender_type'] == 'user'), "Нет сообщений")

        pending_chats.append({
            'chat_id': chat['id'],
            'email': chat['user_email'],
            'last_message': last_msg
        })

    return jsonify({'success': True, 'chats': pending_chats})

# 5. Панель Администратора: Подключение к чату
@app.route('/api/admin/connect', methods=['POST'])
def connect_to_chat():
    data = request.json or {}
    chat_id = data.get('chat_id')

    # Меняем статус на 'agent_connected'
    supabase.table('support_chats').update({'status': 'agent_connected'}).eq('id', chat_id).execute()

    # Уведомляем пользователя
    supabase.table('support_messages').insert({
        'chat_id': chat_id,
        'sender_type': 'bot',
        'message': 'Специалист подключился к чату и готов вам помочь!'
    }).execute()

    return jsonify({'success': True, 'message': 'Connected to chat successfully'})
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
