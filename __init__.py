import os
from flask import Flask
from .config import Config
from .extensions import db, mail, oauth

# Resolve paths relative to this file so they work both locally and on Render
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_FRONTEND_DIR = os.path.join(_BASE_DIR, 'frontend')

def create_app(config_class=Config):
    app = Flask(__name__,
                template_folder=os.path.join(_FRONTEND_DIR, 'templates'),
                static_folder=os.path.join(_FRONTEND_DIR, 'static'))
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    mail.init_app(app)
    oauth.init_app(app)
    
    # Register Google OAuth
    oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        server_metadata_url=app.config.get('GOOGLE_DISCOVERY_URL'),
        client_kwargs={'scope': 'openid email profile'},
        jwt_config={'leeway': 604800} # Provide a 7-day leeway to bypass local time sync issues
    )
    
    # Register Blueprints
    from .routes import auth, main, transactions, savings, fincoach, family
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(transactions.bp)
    app.register_blueprint(savings.bp)
    app.register_blueprint(fincoach.bp)
    app.register_blueprint(family.bp)
    
    return app
