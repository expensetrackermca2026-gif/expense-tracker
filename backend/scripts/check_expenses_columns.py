from backend import create_app
from backend.extensions import db
from sqlalchemy import text, inspect

app = create_app()
with app.app_context():
    try:
        inspector = inspect(db.engine)
        columns = inspector.get_columns('expenses')
        print("Columns in 'expenses' table:")
        for column in columns:
            print(f"- {column['name']}")
    except Exception as e:
        print(f"Error checking columns: {e}")
