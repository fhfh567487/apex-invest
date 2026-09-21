from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# Имитация базы данных пользователей и депозитов в памяти
user_data = {
    "balance": 2000.0,
    "deposits": []
}

def process_daily_accruals():
    """Автоматически начисляет 15% в день за каждые прошедшие 24 часа"""
    now = datetime.now()
    for deposit in user_data["deposits"]:
        if deposit["status"] == "active":
            last_accrual = datetime.fromisoformat(deposit["last_accrual"])
            elapsed_days = (now - last_accrual).days

            if elapsed_days >= 1 and deposit["days_left"] > 0:
                days_to_pay = min(elapsed_days, deposit["days_left"])
                
                # 450% / 30 дней = 15% в день
                daily_profit = deposit["amount"] * (deposit["daily_percent"] / 100.0)
                payout = daily_profit * days_to_pay

                # Пополнение баланса
                user_data["balance"] += payout
                deposit["days_left"] -= days_to_pay
                
                # Обновление даты последнего начисления
                new_accrual = last_accrual + timedelta(days=days_to_pay)
                deposit["last_accrual"] = new_accrual.isoformat()

                if deposit["days_left"] <= 0:
                    deposit["status"] = "completed"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/user", methods=["GET"])
def get_user_data():
    process_daily_accruals()  # Проверяем начисления при каждом запросе
    return jsonify(user_data)

@app.route("/api/invest", methods=["POST"])
def invest():
    data = request.get_json()
    amount = float(data.get("amount", 0))

    if amount <= 0 or amount > user_data["balance"]:
        return jsonify({"error": "Недостаточно средств на балансе!"}), 400

    user_data["balance"] -= amount
    
    start_time = datetime.now()
    end_time = start_time + timedelta(days=30)
    
    new_deposit = {
        "id": len(user_data["deposits"]) + 1,
        "amount": amount,
        "daily_percent": 15.0,  # 15% в день
        "days_total": 30,
        "days_left": 30,
        "start_date": start_time.isoformat(),
        "end_date": end_time.isoformat(),
        "last_accrual": start_time.isoformat(),
        "status": "active"
    }
    
    user_data["deposits"].append(new_deposit)
    return jsonify({"success": True, "deposit": new_deposit, "balance": user_data["balance"]})

if __name__ == "__main__":
    app.run(debug=True)
