from backend import create_app
from backend.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE expenses ADD COLUMN statement_tag VARCHAR(100)"))
        db.session.commit()
        print("Column statement_tag added successfully.")
    except Exception as e:
        print(f"Error or column already exists: {e}")
