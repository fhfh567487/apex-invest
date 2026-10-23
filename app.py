from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
import os

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "ТВОЙ_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "ТВОЙ_SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ------------------------------------
# ЧАТ ПОДДЕРЖКИ API
# ------------------------------------

# 1. Получение или создание чата
@app.route('/api/support/init', methods=['POST'])
def init_chat():
    data = request.json
    email = data.get('email', 'guest@apexinvest.com')
    
    # Ищем активный чат пользователя
    res = supabase.table('support_chats').select('*').eq('user_email', email).neq('status', 'closed').execute()
    
    if res.data:
        chat = res.data[0]
    else:
        # Создаем новый
        chat_res = supabase.table('support_chats').insert({'user_email': email, 'status': 'bot'}).execute()
        chat = chat_res.data[0]
        
        # Начальное приветствие от бота
        supabase.table('support_messages').insert({
            'chat_id': chat['id'],
            'sender_type': 'bot',
            'message': 'Здравствуйте! Я ИИ-ассистент Apex Invest. Чем я могу вам помочь?'
        }).execute()

    return jsonify({'success': True, 'chat': chat})

# 2. Вызов специалиста (переключение режима)
@app.route('/api/support/call-agent', methods=['POST'])
def call_agent():
    data = request.json
    chat_id = data.get('chat_id')
    
    # Обновляем статус чата
    supabase.table('support_chats').update({'status': 'waiting_for_agent'}).eq('id', chat_id).execute()
    
    # Отправляем сообщение от бота
    msg_res = supabase.table('support_messages').insert({
        'chat_id': chat_id,
        'sender_type': 'bot',
        'message': 'Специалист вызван, ожидайте подключения...'
    }).execute()
    
    return jsonify({'success': True, 'message': msg_res.data[0]})

# 3. Обработка сообщения от пользователя
@app.route('/api/support/send', methods=['POST'])
def send_message():
    data = request.json
    chat_id = data.get('chat_id')
    text = data.get('message')
    
    # Сохраняем сообщение пользователя
    user_msg = supabase.table('support_messages').insert({
        'chat_id': chat_id,
        'sender_type': 'user',
        'message': text
    }).execute()
    
    # Проверяем статус чата
    chat_res = supabase.table('support_chats').select('status').eq('id', chat_id).execute()
    status = chat_res.data[0]['status'] if chat_res.data else 'bot'
    
    # Если чат с ботом — генерируем ответ ИИ
    if status == 'bot':
        ai_reply = f"Я ИИ-ассистент Apex Invest. Насчет '{text}': вы можете изучить наши тарифы или вызвать специалиста для личной консультации."
        
        bot_msg = supabase.table('support_messages').insert({
            'chat_id': chat_id,
            'sender_type': 'bot',
            'message': ai_reply
        }).execute()
        
        return jsonify({'success': True, 'bot_reply': bot_msg.data[0]})
    
    # Если статус 'waiting_for_agent' или 'active_agent' — бот молчит, сообщение ждет ответа админа
    return jsonify({'success': True, 'status': status})

# Страница Админки чатов
@app.route('/admin/support')
def admin_support():
    return render_template('admin_support.html')

if __name__ == '__main__':
    app.run(debug=True)
