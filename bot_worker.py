"""
Отдельный процесс только для Telegram-бота.
Не умирает вместе с gunicorn worker.

Запуск: python bot_worker.py
В Procfile: worker: python bot_worker.py
"""
import os
import sys
import time

# Не поднимать второй polling при import app
os.environ["RUN_BOT"] = "0"

from dotenv import load_dotenv

load_dotenv()

# Импорт после RUN_BOT=0 — handlers зарегистрируются, поток не стартует
from app import bot, run_bot_polling, BOT_TOKEN, BOT_USERNAME

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN не задан. Укажи в Environment Variables.")
        sys.exit(1)
    if not bot:
        print("❌ Не удалось создать TeleBot")
        sys.exit(1)

    print(f"✅ Worker started for @{BOT_USERNAME}")
    print("📡 Polling in MAIN process (not a daemon thread)")

    # Бесконечный цикл с перезапуском — процесс живёт, пока жив worker dyno
    while True:
        try:
            run_bot_polling()
        except KeyboardInterrupt:
            print("Stopped by user")
            break
        except Exception as e:
            print(f"❌ Fatal in worker: {type(e).__name__}: {e}")
            print("⏳ Restart in 5 sec...")
            time.sleep(5)
