import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)  # Разрешаем cross-origin запросы с GitHub Pages

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://bycfzzqpnnsqgwtzccdc.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "sb_publishable_sYHXSnwWJgT178wtP8MISA_t7A030f2")

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
            'message': 'Здравствуйте! Я ИИ-ассистент Apex Invest. Чем могу вам помочь?'
        }).execute()

    return jsonify({'success': True, 'chat': chat})

# 2. Вызов специалиста
@app.route('/api/support/call-agent', methods=['POST'])
def call_agent():
    data = request.json or {}
    chat_id = data.get('chat_id')
    
    supabase.table('support_chats').update({'status': 'waiting_for_agent'}).eq('id', chat_id).execute()
    
    msg_res = supabase.table('support_messages').insert({
        'chat_id': chat_id,
        'sender_type': 'bot',
        'message': 'Специалист вызван, ожидайте подключения...'
    }).execute()
    
    return jsonify({'success': True, 'message': msg_res.data[0]})

# 3. Отправка сообщений
@app.route('/api/support/send', methods=['POST'])
def send_message():
    data = request.json or {}
    chat_id = data.get('chat_id')
    text = data.get('message', '')
    
    supabase.table('support_messages').insert({
        'chat_id': chat_id,
        'sender_type': 'user',
        'message': text
    }).execute()
    
    chat_res = supabase.table('support_chats').select('status').eq('id', chat_id).execute()
    status = chat_res.data[0]['status'] if chat_res.data else 'bot'
    
    if status == 'bot':
        ai_reply = f"Спасибо за вопрос по теме '{text}'. Пожалуйста, выберите нужный инвестиционный план на сайте или нажмите кнопку вызова специалиста!"
        
        bot_msg = supabase.table('support_messages').insert({
            'chat_id': chat_id,
            'sender_type': 'bot',
            'message': ai_reply
        }).execute()
        
        return jsonify({'success': True, 'bot_reply': bot_msg.data[0]})
    
    return jsonify({'success': True, 'status': status})

# Страница оператора (для тебя)
@app.route('/admin/support')
def admin_support():
    return render_template('admin_support.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
