web: gunicorn -w 1 --threads 4 -b 0.0.0.0:$PORT app:app --timeout 120
worker: python bot_worker.py