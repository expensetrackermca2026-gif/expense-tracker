import os
import sys

# Add backend to path just in case
sys.path.append(os.getcwd())

try:
    from backend import create_app
    from backend.extensions import db
    from backend.models import User, Expense, FamilyGroup, FamilyMember, LoginAudit, AnomalyWarning
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

from sqlalchemy import text

app = create_app()
with app.app_context():
    print("App context active. Creating tables...")
    try:
        db.create_all()
        print("db.create_all() finished.")
    except Exception as e:
        print(f"Error in create_all: {e}")

    print("Checking column additions...")
    # Column check and addition
    queries = [
        "ALTER TABLE expenses ADD COLUMN IF NOT EXISTS group_id UUID REFERENCES family_groups(id);",
        "ALTER TABLE anomaly_warnings ADD COLUMN IF NOT EXISTS amount_diff NUMERIC(15, 2);",
        "ALTER TABLE anomaly_warnings ADD COLUMN IF NOT EXISTS percentage_spike NUMERIC(15, 2);"
    ]
    
    for q in queries:
        try:
            db.session.execute(text(q))
            db.session.commit()
            print(f"Success/Exists: {q}")
        except Exception as e:
            db.session.rollback()
            print(f"Query '{q}' failed: {e}")

    print("Sync script finished.")
