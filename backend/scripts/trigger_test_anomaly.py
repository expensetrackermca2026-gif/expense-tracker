from backend import create_app
from backend.extensions import db
from backend.models import User, Expense
from backend.utils import detect_anomalies, runMonthlyEvaluation
from datetime import datetime

app = create_app()
with app.app_context():
    # Find test user
    u = User.query.filter_by(email='test@example.com').first()
    if u:
        # 1. Create a baseline of normal expenses
        for i in range(5):
            e = Expense(user_id=u.id, title="Coffee", amount=150.0, category="Food & Drinks", type="Paid")
            db.session.add(e)
        db.session.commit()
        
        # 2. Create a LARGE anomaly
        anomaly = Expense(user_id=u.id, title="SUSPICIOUS LARGE PURCHASE", amount=50000.0, category="Others", type="Paid")
        db.session.add(anomaly)
        db.session.commit()
        
        # 3. Trigger detector
        detect_anomalies(u.id, anomaly.id)
        runMonthlyEvaluation(u.id)
        
        print(f"Anomaly triggered for user {u.email}")
    else:
        print("User not found.")
