from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from ..extensions import db, mail, oauth
from ..models import User, UserAuthProvider, AuthProviderType
import random

bp = Blueprint('auth', __name__)

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if user exists via email
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('auth.signup'))

        otp = str(random.randint(1000, 9999))
        session['otp'] = otp
        session['temp_user'] = {
            'name': name, 'email': email, 
            'password': generate_password_hash(password)
        }

        try:
            msg = Message('Expense Analyzer OTP', sender=current_app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = f"Hi {name}, unga verification OTP: {otp}"
            mail.send(msg)
            flash('OTP sent to your email!', 'info')
            return redirect(url_for('auth.verify'))
        except Exception as e:
            flash(f"Mail Error: Could not send email. {str(e)}", 'danger')
            return redirect(url_for('auth.signup'))
    return render_template('signup.html')

@bp.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'temp_user' not in session: return redirect(url_for('auth.signup'))
    if request.method == 'POST':
        if request.form.get('otp') == session.get('otp'):
            data = session.get('temp_user')
            
            # Create User
            new_user = User(full_name=data['name'], email=data['email'], is_verified=True)
            db.session.add(new_user)
            db.session.flush() # Ensure ID is generated
            
            # Create Auth Provider
            new_auth = UserAuthProvider(
                user_id=new_user.id, 
                provider=AuthProviderType.EMAIL, 
                provider_user_id=data['email'], 
                password_hash=data['password']
            )
            db.session.add(new_auth)
            db.session.commit()
            
            session.pop('otp', None); session.pop('temp_user', None)
            flash('Registration Success! Login now.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid OTP!', 'danger')
    return render_template('verify.html', email=session['temp_user']['email'])

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user:
            # Check for EMAIL provider
            auth_provider = UserAuthProvider.query.filter_by(
                user_id=user.id, 
                provider=AuthProviderType.EMAIL
            ).first()
            
            if auth_provider and check_password_hash(auth_provider.password_hash, password):
                session['user_id'] = str(user.id) # Convert UUID to string for session
                session['user_name'] = user.full_name
                
                # Log login success (optional, based on new schema capabilities)
                return redirect(url_for('main.index'))
                
        flash('Invalid Credentials!', 'danger')
    return render_template('login.html')

@bp.route('/logout')
def logout(): 
    session.clear() 
    return redirect(url_for('auth.login'))

@bp.route('/login/google')
def google_login():
    redirect_uri = url_for('auth.google_authorize', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@bp.route('/login/google/authorize')
def google_authorize():
    try:
        token = oauth.google.authorize_access_token()
        user_info = oauth.google.userinfo()
        email = user_info['email']
        name = user_info['name']
        sub = user_info.get('sub', email) # Use 'sub' as strict ID, fallback to email

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, full_name=name, is_verified=True)
            db.session.add(user)
            db.session.flush()
        
        # Check/Add Auth Provider
        auth = UserAuthProvider.query.filter_by(user_id=user.id, provider=AuthProviderType.GOOGLE).first()
        if not auth:
            auth = UserAuthProvider(
                user_id=user.id, 
                provider=AuthProviderType.GOOGLE, 
                provider_user_id=sub
            )
            db.session.add(auth)
            db.session.commit()
        
        session['user_id'] = str(user.id)
        session['user_name'] = user.full_name
        return redirect(url_for('main.index'))
    except Exception as e:
        flash(f"Google Login Failed: {str(e)}", 'danger')
        return redirect(url_for('auth.login'))
