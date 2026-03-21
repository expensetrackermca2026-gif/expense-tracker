import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from flask import Flask
from sqlalchemy import text
from backend.extensions import db
from backend.config import Config

def check_db_connection():
    print("--- Database Connection Check ---")
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    print(f"Target DB URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

    try:
        with app.app_context():
            # Try a simple query
            result = db.session.execute(text('SELECT 1')).scalar()
            print(f"Connection Successful! Test Query Result: {result}")
            
            # Check if tables exist
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Existing Tables: {tables}")
            
            if not tables:
                print("WARNING: Database connected but NO tables found.")
                print("You might need to initialize the schema.")
                print("Attempting to create tables now...")
                db.create_all()
                print("Tables created successfully (User, Expense, etc.)")
            else:
                print("Schema looks present.")
                
            return True
            
    except Exception as e:
        print(f"❌ DATABASE CONNECTION FAILED: {str(e)}")
        return False

if __name__ == "__main__":
    if check_db_connection():
        print("--- READY TO START ---")
    else:
        print("--- FIX DATABASE ERROR BEFORE RUNNING ---")
        exit(1)
