import sys
import os
# Add the root directory to sys.path to resolve backend package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend import create_app
from backend.extensions import db
from backend import models

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Ideally use Flask-Migrate for production
        db.create_all()
        
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
    app.run(debug=True)
