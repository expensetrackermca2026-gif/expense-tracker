import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key_if_missing')
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or 'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'expense_oracle_master.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,  # Recycle connections every 30 minutes
    }
    
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    
    # Adjusted path for uploads in the new frontend folder
    UPLOAD_FOLDER = os.path.abspath(os.path.join(BASE_DIR, '..', 'frontend', 'static', 'uploads'))
    
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

    # Business Logic
    MICRO_PERCENT = float(os.getenv('MICRO_PERCENT', 50))
    SAFE_PERCENT = float(os.getenv('SAFE_PERCENT', 30))
    GROWTH_PERCENT = float(os.getenv('GROWTH_PERCENT', 20))
