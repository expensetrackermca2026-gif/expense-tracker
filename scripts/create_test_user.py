import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend import create_app
from backend.extensions import db
from backend.models import User, UserAuthProvider, AuthProviderType
from werkzeug.security import generate_password_hash
import uuid

app = create_app()
with app.app_context():
    email = "test@example.com"
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        print(f"User already exists with ID: {existing_user.id}")
    else:
        new_user = User(
            full_name="Test User",
            email=email,
            is_verified=True,
            savings_goal=1000.0,
            monthly_income=5000.0
        )
        db.session.add(new_user)
        db.session.flush()
        
        new_auth = UserAuthProvider(
            user_id=new_user.id,
            provider=AuthProviderType.EMAIL,
            provider_user_id=email,
            password_hash=generate_password_hash("password123")
        )
        db.session.add(new_auth)
        db.session.commit()
        print(f"User created with ID: {new_user.id}")
