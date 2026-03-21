from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from authlib.integrations.flask_client import OAuth

db = SQLAlchemy()
mail = Mail()
oauth = OAuth()
