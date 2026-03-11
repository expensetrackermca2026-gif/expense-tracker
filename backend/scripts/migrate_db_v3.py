from backend import create_app
from backend.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    alterations = [
        "ALTER TABLE expenses ADD COLUMN ai_category_suggestion VARCHAR(50)",
        "ALTER TABLE expenses ADD COLUMN is_anomaly BOOLEAN DEFAULT FALSE",
        
        # New Tables
        """
        CREATE TABLE IF NOT EXISTS ai_reports (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(50),
            year INTEGER,
            month INTEGER,
            content TEXT,
            data_snapshot JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS investment_plans (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            savings_goal NUMERIC(15, 2),
            plan_json JSONB,
            advice_text TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS anomaly_warnings (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expense_id UUID REFERENCES expenses(id) ON DELETE CASCADE,
            type VARCHAR(50),
            reason TEXT,
            is_resolved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """
    ]
    
    for sql in alterations:
        try:
            db.session.execute(text(sql))
            db.session.commit()
            print(f"Executed OK: {sql[:50]}...")
        except Exception as e:
            db.session.rollback()
            print(f"Skipped/Error: {sql[:50]}... | {e}")
