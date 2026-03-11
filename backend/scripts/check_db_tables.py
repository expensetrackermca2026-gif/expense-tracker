from backend import create_app
from backend.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        result = db.session.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';"))
        tables = result.fetchall()
        print("Tables in database:", [table[0] for table in tables])
    except Exception as e:
        print(f"Error checking tables: {e}")
