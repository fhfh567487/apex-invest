from datetime import datetime, timedelta

class InvestmentDeposit:
    PLAN_CONFIGS = {
        'Novice': {'days': 1, 'total_profit_pct': 0.12, 'daily_pct': 0.12},
        'Pro': {'days': 10, 'total_profit_pct': 2.50, 'daily_pct': 0.25},
        'Master': {'days': 30, 'total_profit_pct': 4.50, 'daily_pct': 0.15}  # 450% / 30 = 15% в день
    }

    def __init__(self, plan_name: str, amount: float):
        if plan_name not in self.PLAN_CONFIGS:
            raise ValueError(f"План {plan_name} не найден")
            
        self.plan_name = plan_name
        self.amount = amount
        self.config = self.PLAN_CONFIGS[plan_name]
        
        self.total_days = self.config['days']
        self.daily_pct = self.config['daily_pct']
        self.daily_profit = amount * self.daily_pct
        
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(days=self.total_days)
        self.days_paid = 0
        self.is_completed = False

    def get_formatted_remaining_time() -> str:
        """Отображает оставшееся время в днях и часах без секунд."""
        now = datetime.now()
        if now >= self.end_time:
            return "Выплачено"

        diff = self.end_time - now
        total_hours = int(diff.total_seconds() // 3600)
        days = total_hours // 24
        hours = total_hours % 24

        if days > 0:
            return f"{days} дн {hours} ч"
        else:
            minutes = int((diff.total_seconds() % 3600) // 60)
            return f"{hours} ч {minutes} мин"

    def process_accrual(self, user_balance: float, total_profit: float):
        """Ежедневное начисление процентов и возврат тела в конце срока."""
        if self.is_completed:
            return user_balance, total_profit

        now = datetime.now()
        days_passed = int((now - self.start_time).total_seconds() // 86400)
        due_days = min(self.total_days, days_passed) - self.days_paid

        if due_days > 0:
            for _ in range(due_days):
                user_balance += self.daily_profit
                total_profit += self.daily_profit
                self.days_paid += 1

        if self.days_paid >= self.total_days:
            user_balance += self.amount  # Возврат тела депозита
            self.is_completed = True

        return user_balance, total_profit
