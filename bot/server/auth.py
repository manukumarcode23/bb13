from quart import Blueprint, request, render_template, redirect, session, jsonify, url_for
from bot.database import AsyncSessionLocal
from bot.models import Publisher
from sqlalchemy import select
from datetime import datetime, timezone
import bcrypt
import re

bp = Blueprint('auth', __name__)

def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

@bp.route('/register', methods=['GET'])
async def register_page():
    if 'publisher_id' in session:
        return redirect('/publisher/dashboard')
    return await render_template('register.html')

@bp.route('/register', methods=['POST'])
async def register():
    data = await request.form
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    traffic_source = data.get('traffic_source', '').strip()
    
    if not all([email, password, confirm_password, traffic_source]):
        return await render_template('register.html', error='All fields are required')
    
    if not is_valid_email(email):
        return await render_template('register.html', error='Invalid email format')
    
    if password != confirm_password:
        return await render_template('register.html', error='Passwords do not match')
    
    if len(password) < 6:
        return await render_template('register.html', error='Password must be at least 6 characters')
    
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(Publisher).where(Publisher.email == email)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                return await render_template('register.html', error='Email already registered')
            
            password_hash = hash_password(password)
            
            publisher = Publisher(
                email=email,
                password_hash=password_hash,
                traffic_source=traffic_source,
                is_admin=False,
                is_active=True
            )
            
            db_session.add(publisher)
            await db_session.commit()
            await db_session.refresh(publisher)
            
            session['publisher_id'] = publisher.id
            session['publisher_email'] = publisher.email
            session['is_admin'] = publisher.is_admin
            
            return redirect('/publisher/dashboard')
            
        except Exception as e:
            await db_session.rollback()
            return await render_template('register.html', error='Registration failed. Please try again.')

@bp.route('/login', methods=['GET'])
async def login_page():
    if 'publisher_id' in session:
        return redirect('/publisher/dashboard')
    return await render_template('login.html')

@bp.route('/login', methods=['POST'])
async def login():
    data = await request.form
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not email or not password:
        return await render_template('login.html', error='Email and password are required')
    
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(Publisher).where(Publisher.email == email)
            )
            publisher = result.scalar_one_or_none()
            
            if not publisher:
                return await render_template('login.html', error='Invalid email or password')
            
            if not publisher.is_active:
                return await render_template('login.html', error='Account is disabled')
            
            if not verify_password(password, publisher.password_hash):
                return await render_template('login.html', error='Invalid email or password')
            
            publisher.last_login = datetime.now(timezone.utc)
            await db_session.commit()
            
            session['publisher_id'] = publisher.id
            session['publisher_email'] = publisher.email
            session['is_admin'] = publisher.is_admin
            
            if publisher.is_admin:
                return redirect('/admin/dashboard')
            else:
                return redirect('/publisher/dashboard')
            
        except Exception as e:
            await db_session.rollback()
            return await render_template('login.html', error='Login failed. Please try again.')

@bp.route('/logout')
async def logout():
    session.clear()
    return redirect('/login')
