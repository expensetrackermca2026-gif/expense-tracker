from backend import create_app
from backend.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # 1. Create all missing tables (FamilyGroup, FamilyMember, LoginAudit)
    db.create_all()
    
    # 2. Add missing columns to 'expenses'
    try:
        db.session.execute(text("ALTER TABLE expenses ADD COLUMN group_id UUID REFERENCES family_groups(id);"))
        db.session.commit()
        print("Added group_id to expenses.")
    except Exception as e:
        db.session.rollback()
        print(f"group_id column ignored (possibly already exists): {e}")

    # 3. Add missing columns to 'anomaly_warnings'
    try:
        db.session.execute(text("ALTER TABLE anomaly_warnings ADD COLUMN amount_diff NUMERIC(15, 2);"))
        db.session.execute(text("ALTER TABLE anomaly_warnings ADD COLUMN percentage_spike NUMERIC(15, 2);"))
        db.session.commit()
        print("Added anomaly metrics to anomaly_warnings.")
    except Exception as e:
        db.session.rollback()
        print(f"Anomaly columns ignored (possibly already exists): {e}")

    print("Database schema synchronization finished.")
