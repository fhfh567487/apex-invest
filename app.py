if message_text or image_data:
        # 1. Сохраняем сообщение пользователя
        chat_messages_memory[session_id].append({"sender": "user", "text": message_text, "image": image_data})
        
        # 2. Отправляем уведомление администратору в Telegram
        send_telegram_notification(session_id, message_text, image_data)

        # 3. Отвечаем пользователю ТОЛЬКО если чат в режиме AI бота (не переключен на оператора)
        if current_state["status"] == "ai":
            text_lower = message_text.lower()
            
            # Логика ключевых слов
            if any(word in text_lower for word in ["вывести", "вывод", "деньги", "снять"]):
                ai_reply = "💰 **Инструкция по выводу средств:**\n1. Перейдите в раздел **Dashboard**.\n2. Убедитесь, что статус **KYC: Verified**.\n3. Нажмите кнопку **Request Withdrawal** (от $10)."
            elif any(word in text_lower for word in ["пополнить", "депозит", "инвестировать", "внести"]):
                ai_reply = "🚀 **Как открыть депозит:**\n1. Выберите тариф на главной странице.\n2. Укажите сумму и нажмите **Invest**.\n3. Переведите средства по указанным реквизитам."
            else:
                ai_reply = "Спасибо за обращение! Ваше сообщение передано оператору поддержки. Пожалуйста, ожидайте ответа."

            # Добавляем ответ поддержки
            chat_messages_memory[session_id].append({
                "sender": "support", 
                "text": ai_reply, 
                "show_buttons": True
            })
