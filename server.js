require('dotenv').config();
const express = require('express');
const cors = require('cors');
const TelegramBot = require('node-telegram-bot-api');

const app = express();
app.use(express.json());
app.use(cors());

const token = process.env.TELEGRAM_BOT_TOKEN;
const bot = new TelegramBot(token, { polling: true });

// Временное хранилище связок (в реальном проекте используйте базу данных MySQL/PostgreSQL/MongoDB)
const pendingConnections = new Map(); // code -> userId
const userTelegramMap = new Map();    // userId -> telegramChatId

// 1. ИНИЦИАЛИЗАЦИЯ БОТА (Обработка /start с кодом)
bot.onText(/\/start(?:\s+(.+))?/, (msg, match) => {
    const chatId = msg.chat.id;
    const authCode = match[1]; // Код из реферальной ссылки бота (например: TG-8492)

    if (authCode && pendingConnections.has(authCode)) {
        const userId = pendingConnections.get(authCode);
        userTelegramMap.set(userId, chatId);
        pendingConnections.delete(authCode);

        bot.sendMessage(chatId, `🎉 *Аккаунт Apex успешно привязан!*\n\nТеперь вы будете получать мгновенные уведомления о депозитах, выводах и начислении процентов.`, {
            parse_mode: 'Markdown'
        });
    } else {
        bot.sendMessage(chatId, `👋 *Добро пожаловать в Apex Official Bot!*\n\nЧтобы привязать аккаунт, нажмите кнопку «Подключить бота» в личном кабинете на сайте.`, {
            parse_mode: 'Markdown'
        });
    }
});

// 2. API: Генерация временного кода для подключения бота
app.post('/api/telegram/generate-code', (req, res) => {
    const { userId } = req.body;
    if (!userId) {
        return res.status(400).json({ error: 'User ID is required' });
    }

    // Генерируем случайный код вида TG-XXXXXX
    const code = 'TG-' + Math.floor(100000 + Math.random() * 900000);
    pendingConnections.set(code, userId);

    const botUsername = process.env.TELEGRAM_BOT_USERNAME || 'ApexOfficialBot';
    const link = `https://t.me/${botUsername}?start=${code}`;

    res.json({ success: true, code, link });
});

// 3. API: Отправка уведомления пользователю
app.post('/api/telegram/notify', (req, res) => {
    const { userId, message } = req.body;
    const chatId = userTelegramMap.get(userId);

    if (!chatId) {
        return res.status(404).json({ error: 'Telegram account not linked for this user' });
    }

    bot.sendMessage(chatId, message, { parse_mode: 'Markdown' })
        .then(() => res.json({ success: true }))
        .catch(err => res.status(500).json({ error: err.message }));
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🚀 Apex Backend Server запущен на порту ${PORT}`);
});
