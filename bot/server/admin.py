from quart import Blueprint, request, render_template, redirect, session, jsonify
from bot.database import AsyncSessionLocal
from bot.models import Publisher, File, AdNetwork, Settings, WithdrawalRequest, BankAccount
from sqlalchemy import select, func
from datetime import datetime
from os import environ
import bcrypt

bp = Blueprint('admin', __name__, url_prefix='/admin')

def require_admin(func):
    async def wrapper(*args, **kwargs):
        if 'publisher_id' not in session:
            return redirect('/login')
        if not session.get('is_admin'):
            return redirect('/publisher/dashboard')
        return await func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

@bp.route('/dashboard')
@require_admin
async def dashboard():
    async with AsyncSessionLocal() as db_session:
        publisher_count = await db_session.scalar(
            select(func.count(Publisher.id))
        )
        file_count = await db_session.scalar(
            select(func.count(File.id))
        )
        
        result = await db_session.execute(
            select(Publisher).order_by(Publisher.created_at.desc())
        )
        publishers = result.scalars().all()
        
    return await render_template('admin_dashboard.html', 
                                  active_page='dashboard',
                                  publishers=publishers,
                                  publisher_count=publisher_count,
                                  file_count=file_count)

@bp.route('/register-publisher', methods=['POST'])
@require_admin
async def register_publisher():
    data = await request.form
    email = data.get('email', '').strip()
    password = data.get('password', '')
    traffic_source = data.get('traffic_source', '').strip()
    is_admin = data.get('is_admin') == 'on'
    
    async with AsyncSessionLocal() as db_session:
        publisher_count = await db_session.scalar(
            select(func.count(Publisher.id))
        )
        file_count = await db_session.scalar(
            select(func.count(File.id))
        )
        result = await db_session.execute(
            select(Publisher).order_by(Publisher.created_at.desc())
        )
        publishers = result.scalars().all()
        
        if not all([email, password, traffic_source]):
            return await render_template('admin_dashboard.html', 
                                          active_page='dashboard',
                                          publishers=publishers,
                                          publisher_count=publisher_count,
                                          file_count=file_count,
                                          error='All fields are required')
        
        try:
            result = await db_session.execute(
                select(Publisher).where(Publisher.email == email)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                return await render_template('admin_dashboard.html', 
                                              active_page='dashboard',
                                              publishers=publishers,
                                              publisher_count=publisher_count,
                                              file_count=file_count,
                                              error='Email already registered')
            
            password_hash = hash_password(password)
            
            publisher = Publisher(
                email=email,
                password_hash=password_hash,
                traffic_source=traffic_source,
                is_admin=is_admin,
                is_active=True
            )
            
            db_session.add(publisher)
            await db_session.commit()
            
            return redirect('/admin/dashboard')
            
        except Exception as e:
            await db_session.rollback()
            return await render_template('admin_dashboard.html', 
                                          active_page='dashboard',
                                          publishers=publishers,
                                          publisher_count=publisher_count,
                                          file_count=file_count,
                                          error='Registration failed')

@bp.route('/toggle-publisher/<int:publisher_id>', methods=['POST'])
@require_admin
async def toggle_publisher(publisher_id):
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(Publisher).where(Publisher.id == publisher_id)
            )
            publisher = result.scalar_one_or_none()
            
            if publisher:
                publisher.is_active = not publisher.is_active
                await db_session.commit()
            
            return redirect('/admin/dashboard')
            
        except Exception as e:
            await db_session.rollback()
            return redirect('/admin/dashboard')

@bp.route('/publishers')
@require_admin
async def publishers():
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            select(Publisher).order_by(Publisher.created_at.desc())
        )
        publishers = result.scalars().all()
        
        publisher_files = {}
        for publisher in publishers:
            file_count = await db_session.scalar(
                select(func.count(File.id)).where(File.publisher_id == publisher.id)
            )
            publisher_files[publisher.id] = file_count
        
    return await render_template('admin_publishers.html', 
                                  active_page='publishers',
                                  publishers=publishers,
                                  publisher_files=publisher_files)

@bp.route('/publisher/<int:publisher_id>/files')
@require_admin
async def publisher_files(publisher_id):
    search_hash = request.args.get('search', '').strip()
    
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            select(Publisher).where(Publisher.id == publisher_id)
        )
        publisher = result.scalar_one_or_none()
        
        if not publisher:
            return redirect('/admin/publishers')
        
        query = select(File).where(File.publisher_id == publisher_id)
        
        if search_hash:
            query = query.where(File.access_code.ilike(f'%{search_hash}%'))
        
        query = query.order_by(File.created_at.desc())
        result = await db_session.execute(query)
        files = result.scalars().all()
        
    return await render_template('admin_publisher_files.html', 
                                  active_page='publishers',
                                  publisher=publisher,
                                  files=files,
                                  search_hash=search_hash)

@bp.route('/delete-file/<int:file_id>', methods=['POST'])
@require_admin
async def delete_file(file_id):
    publisher_id = request.args.get('publisher_id')
    
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(File).where(File.id == file_id)
            )
            file = result.scalar_one_or_none()
            
            if file:
                await db_session.delete(file)
                await db_session.commit()
            
            if publisher_id:
                return redirect(f'/admin/publisher/{publisher_id}/files')
            return redirect('/admin/publishers')
            
        except Exception as e:
            await db_session.rollback()
            if publisher_id:
                return redirect(f'/admin/publisher/{publisher_id}/files')
            return redirect('/admin/publishers')

@bp.route('/ad-networks')
@require_admin
async def ad_networks():
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            select(AdNetwork).order_by(AdNetwork.priority)
        )
        networks = result.scalars().all()
        
    api_token = environ.get('AD_API_TOKEN', '')
    return await render_template('admin_ad_networks.html', active_page='ad_networks', networks=networks, api_token=api_token)

@bp.route('/ad-networks/add', methods=['POST'])
@require_admin
async def add_ad_network():
    data = await request.form
    
    async with AsyncSessionLocal() as db_session:
        try:
            network = AdNetwork(
                network_name=data.get('network_name', '').strip(),
                banner_id=data.get('banner_id', '').strip() or None,
                interstitial_id=data.get('interstitial_id', '').strip() or None,
                rewarded_id=data.get('rewarded_id', '').strip() or None,
                banner_daily_limit=int(data.get('banner_daily_limit') or 0),
                interstitial_daily_limit=int(data.get('interstitial_daily_limit') or 0),
                rewarded_daily_limit=int(data.get('rewarded_daily_limit') or 0),
                status=data.get('status', 'active'),
                priority=int(data.get('priority') or 1)
            )
            
            db_session.add(network)
            await db_session.commit()
            
            return redirect('/admin/ad-networks')
            
        except Exception as e:
            await db_session.rollback()
            return redirect('/admin/ad-networks')

@bp.route('/ad-networks/edit/<int:network_id>', methods=['POST'])
@require_admin
async def edit_ad_network(network_id):
    data = await request.form
    
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(AdNetwork).where(AdNetwork.id == network_id)
            )
            network = result.scalar_one_or_none()
            
            if network:
                network.network_name = data.get('network_name', '').strip()
                network.banner_id = data.get('banner_id', '').strip() or None
                network.interstitial_id = data.get('interstitial_id', '').strip() or None
                network.rewarded_id = data.get('rewarded_id', '').strip() or None
                network.banner_daily_limit = int(data.get('banner_daily_limit') or 0)
                network.interstitial_daily_limit = int(data.get('interstitial_daily_limit') or 0)
                network.rewarded_daily_limit = int(data.get('rewarded_daily_limit') or 0)
                network.status = data.get('status', 'active')
                network.priority = int(data.get('priority') or 1)
                
                await db_session.commit()
            
            return redirect('/admin/ad-networks')
            
        except Exception as e:
            await db_session.rollback()
            return redirect('/admin/ad-networks')

@bp.route('/ad-networks/toggle/<int:network_id>', methods=['POST'])
@require_admin
async def toggle_ad_network(network_id):
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(AdNetwork).where(AdNetwork.id == network_id)
            )
            network = result.scalar_one_or_none()
            
            if network:
                network.status = 'inactive' if network.status == 'active' else 'active'
                await db_session.commit()
            
            return redirect('/admin/ad-networks')
            
        except Exception as e:
            await db_session.rollback()
            return redirect('/admin/ad-networks')

@bp.route('/ad-networks/delete/<int:network_id>', methods=['POST'])
@require_admin
async def delete_ad_network(network_id):
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(AdNetwork).where(AdNetwork.id == network_id)
            )
            network = result.scalar_one_or_none()
            
            if network:
                await db_session.delete(network)
                await db_session.commit()
            
            return redirect('/admin/ad-networks')
            
        except Exception as e:
            await db_session.rollback()
            return redirect('/admin/ad-networks')

@bp.route('/settings')
@require_admin
async def settings():
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(select(Settings))
        settings = result.scalar_one_or_none()
        
        if not settings:
            settings = Settings(terms_of_service='', privacy_policy='')
            db_session.add(settings)
            await db_session.commit()
        
    return await render_template('admin_settings.html', active_page='settings', settings=settings)

@bp.route('/settings/update', methods=['POST'])
@require_admin
async def update_settings():
    data = await request.form
    
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(select(Settings))
            settings = result.scalar_one_or_none()
            
            if not settings:
                settings = Settings()
                db_session.add(settings)
            
            settings.terms_of_service = data.get('terms_of_service', '').strip()
            settings.privacy_policy = data.get('privacy_policy', '').strip()
            settings.impression_rate = float(data.get('impression_rate', 0) or 0)
            settings.android_package_name = data.get('android_package_name', '').strip()
            settings.android_deep_link_scheme = data.get('android_deep_link_scheme', '').strip()
            settings.minimum_withdrawal = float(data.get('minimum_withdrawal', 10.0) or 10.0)
            settings.ads_api_token = data.get('ads_api_token', '').strip() or None
            settings.callback_mode = data.get('callback_mode', 'POST').strip()
            
            await db_session.commit()
            
            return redirect('/admin/settings')
            
        except Exception as e:
            await db_session.rollback()
            return redirect('/admin/settings')

@bp.route('/withdrawals')
@require_admin
async def withdrawals():
    status_filter = request.args.get('status', 'all')
    
    async with AsyncSessionLocal() as db_session:
        # Base query
        query = select(WithdrawalRequest).order_by(WithdrawalRequest.requested_at.desc())
        
        # Apply status filter
        if status_filter != 'all':
            query = query.where(WithdrawalRequest.status == status_filter)
        
        result = await db_session.execute(query)
        withdrawal_requests = result.scalars().all()
        
        # Get publisher and bank account info for each request
        withdrawal_data = []
        for wr in withdrawal_requests:
            publisher_result = await db_session.execute(
                select(Publisher).where(Publisher.id == wr.publisher_id)
            )
            publisher = publisher_result.scalar_one_or_none()
            
            bank_result = await db_session.execute(
                select(BankAccount).where(BankAccount.id == wr.bank_account_id)
            )
            bank_account = bank_result.scalar_one_or_none()
            
            withdrawal_data.append({
                'withdrawal': wr,
                'publisher': publisher,
                'bank_account': bank_account
            })
        
        # Get statistics
        total_pending = await db_session.scalar(
            select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.status == 'pending')
        )
        total_approved = await db_session.scalar(
            select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.status == 'approved')
        )
        total_rejected = await db_session.scalar(
            select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.status == 'rejected')
        )
        
    return await render_template('admin_withdrawals.html',
                                  active_page='withdrawals',
                                  withdrawal_data=withdrawal_data,
                                  status_filter=status_filter,
                                  total_pending=total_pending or 0,
                                  total_approved=total_approved or 0,
                                  total_rejected=total_rejected or 0)

@bp.route('/withdrawal/approve/<int:withdrawal_id>', methods=['POST'])
@require_admin
async def approve_withdrawal(withdrawal_id):
    data = await request.form
    admin_note = data.get('admin_note', '').strip()
    
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(WithdrawalRequest).where(WithdrawalRequest.id == withdrawal_id)
            )
            withdrawal = result.scalar_one_or_none()
            
            if withdrawal and withdrawal.status == 'pending':
                # Get publisher and verify balance
                publisher_result = await db_session.execute(
                    select(Publisher).where(Publisher.id == withdrawal.publisher_id)
                )
                publisher = publisher_result.scalar_one_or_none()
                
                if publisher and publisher.balance >= withdrawal.amount:
                    # Sufficient balance - approve withdrawal
                    publisher.balance -= withdrawal.amount
                    withdrawal.status = 'approved'
                    withdrawal.admin_note = admin_note
                    withdrawal.processed_at = datetime.now()
                    
                    await db_session.commit()
                elif publisher:
                    # Insufficient balance - reject automatically with note
                    withdrawal.status = 'rejected'
                    withdrawal.admin_note = f"Insufficient balance. Required: ${withdrawal.amount:.2f}, Available: ${publisher.balance:.2f}. {admin_note}" if admin_note else f"Insufficient balance. Required: ${withdrawal.amount:.2f}, Available: ${publisher.balance:.2f}"
                    withdrawal.processed_at = datetime.now()
                    
                    await db_session.commit()
            
            return redirect('/admin/withdrawals')
            
        except Exception as e:
            await db_session.rollback()
            return redirect('/admin/withdrawals')

@bp.route('/withdrawal/reject/<int:withdrawal_id>', methods=['POST'])
@require_admin
async def reject_withdrawal(withdrawal_id):
    data = await request.form
    admin_note = data.get('admin_note', '').strip()
    
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(WithdrawalRequest).where(WithdrawalRequest.id == withdrawal_id)
            )
            withdrawal = result.scalar_one_or_none()
            
            if withdrawal and withdrawal.status == 'pending':
                withdrawal.status = 'rejected'
                withdrawal.admin_note = admin_note
                withdrawal.processed_at = datetime.now()
                
                await db_session.commit()
            
            return redirect('/admin/withdrawals')
            
        except Exception as e:
            await db_session.rollback()
            return redirect('/admin/withdrawals')
