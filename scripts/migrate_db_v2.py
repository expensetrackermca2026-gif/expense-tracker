from backend import create_app
from backend.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    alterations = [
        "ALTER TABLE expenses ADD COLUMN transaction_hash VARCHAR(64)",
        "CREATE INDEX idx_expenses_transaction_hash ON expenses(transaction_hash)",
        "ALTER TABLE monthly_summaries ADD COLUMN current_balance NUMERIC(15, 2) DEFAULT 0.00",
        "ALTER TABLE monthly_summaries ADD COLUMN last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
    ]
    
    for sql in alterations:
        try:
            db.session.execute(text(sql))
            db.session.commit()
            print(f"Executed: {sql}")
        except Exception as e:
            db.session.rollback()
            print(f"Failed or already exists: {sql} | Error: {e}")
