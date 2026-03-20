import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("Error: DATABASE_URL not found in .env")
    exit(1)

engine = create_engine(db_url)
with engine.connect() as conn:
    print("Connecting to database...")
    try:
        conn.execute(text("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS group_id UUID;"))
        conn.execute(text("ALTER TABLE expenses ADD CONSTRAINT fk_family_group FOREIGN KEY (group_id) REFERENCES family_groups(id);"))
        print("Updated Expenses table.")
    except Exception as e:
        print(f"Expenses update notice: {e}")
        
    try:
        conn.execute(text("ALTER TABLE anomaly_warnings ADD COLUMN IF NOT EXISTS amount_diff NUMERIC(15, 2);"))
        conn.execute(text("ALTER TABLE anomaly_warnings ADD COLUMN IF NOT EXISTS percentage_spike NUMERIC(15, 2);"))
        print("Updated AnomalyWarnings table.")
    except Exception as e:
        print(f"Anomaly update notice: {e}")
    
    conn.commit()
    print("Database Schema Finalized.")
