from flask import Flask
from .config import Config
from .extensions import db, mail, oauth

def create_app(config_class=Config):
    app = Flask(__name__, 
                template_folder='../frontend/templates',
                static_folder='../frontend/static')
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
        client_kwargs={'scope': 'openid email profile'}
    )
    
    # Register Blueprints
    from .routes import auth, main, transactions, savings
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(transactions.bp)

    app.register_blueprint(savings.bp)
    
    return app
