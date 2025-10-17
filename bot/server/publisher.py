from quart import Blueprint, request, render_template, redirect, session, jsonify
from bot.database import AsyncSessionLocal
from bot.models import File, Publisher, PublisherImpression, Settings, BankAccount, WithdrawalRequest
from bot import TelegramBot
from bot.config import Telegram, Server
from bot.modules.telegram import get_message, get_file_properties
from sqlalchemy import select, and_, func
from datetime import datetime, date
from secrets import token_hex
import os
import tempfile
from werkzeug.utils import secure_filename
import logging

bp = Blueprint('publisher', __name__, url_prefix='/publisher')
logger = logging.getLogger('bot.server')

def require_publisher(func):
    async def wrapper(*args, **kwargs):
        if 'publisher_id' not in session:
            return redirect('/login')
        
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(Publisher).where(Publisher.id == session['publisher_id'])
            )
            publisher = result.scalar_one_or_none()
            
            if not publisher or not publisher.is_active:
                session.clear()
                return redirect('/login')
        
        return await func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@bp.route('/dashboard')
@require_publisher
async def dashboard():
    today = date.today()
    
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            select(Publisher).where(Publisher.id == session['publisher_id'])
        )
        publisher = result.scalar_one_or_none()
        
        # Get total files count
        total_files_result = await db_session.execute(
            select(func.count(File.id)).where(File.publisher_id == session['publisher_id'])
        )
        total_files = total_files_result.scalar() or 0
        
        # Get today's files count
        today_files_result = await db_session.execute(
            select(func.count(File.id)).where(
                and_(
                    File.publisher_id == session['publisher_id'],
                    func.date(File.created_at) == today
                )
            )
        )
        today_files = today_files_result.scalar() or 0
        
        # Get total impressions count
        total_impressions_result = await db_session.execute(
            select(func.count(PublisherImpression.id)).where(
                PublisherImpression.publisher_id == session['publisher_id']
            )
        )
        total_impressions = total_impressions_result.scalar() or 0
        
        # Get today's impressions count
        today_impressions_result = await db_session.execute(
            select(func.count(PublisherImpression.id)).where(
                and_(
                    PublisherImpression.publisher_id == session['publisher_id'],
                    PublisherImpression.impression_date == today
                )
            )
        )
        today_impressions = today_impressions_result.scalar() or 0
        
        # Get last 7 days data for graph
        # File uploads by day
        files_result = await db_session.execute(
            select(
                func.date(File.created_at).label('date'),
                func.count(File.id).label('count')
            ).where(
                File.publisher_id == session['publisher_id']
            ).group_by(
                func.date(File.created_at)
            ).order_by(
                func.date(File.created_at).desc()
            ).limit(30)
        )
        files_by_date = {str(row.date): row.count for row in files_result.all()}
        
        # Impressions by day
        impressions_result = await db_session.execute(
            select(
                PublisherImpression.impression_date,
                func.count(PublisherImpression.id).label('count')
            ).where(
                PublisherImpression.publisher_id == session['publisher_id']
            ).group_by(
                PublisherImpression.impression_date
            ).order_by(
                PublisherImpression.impression_date.desc()
            ).limit(30)
        )
        impressions_by_date = {str(row.impression_date): row.count for row in impressions_result.all()}
        
        # Get impression rate from settings
        settings_result = await db_session.execute(select(Settings))
        settings = settings_result.scalar_one_or_none()
        impression_rate = settings.impression_rate if settings else 0.0
        
        # Calculate earnings
        today_earnings = today_impressions * impression_rate
        total_earnings = total_impressions * impression_rate
        
        # Create combined date list for last 30 days
        from datetime import timedelta
        dates = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
        
        chart_labels = dates
        chart_files_data = [files_by_date.get(d, 0) for d in dates]
        chart_impressions_data = [impressions_by_date.get(d, 0) for d in dates]
        chart_earnings_data = [float(impressions_by_date.get(d, 0)) * impression_rate for d in dates]
        
    return await render_template('publisher_dashboard.html', 
                                  active_page='dashboard',
                                  email=session['publisher_email'],
                                  balance=publisher.balance if publisher else 0.0,
                                  total_files=total_files,
                                  today_files=today_files,
                                  total_impressions=total_impressions,
                                  today_impressions=today_impressions,
                                  today_earnings=today_earnings,
                                  total_earnings=total_earnings,
                                  impression_rate=impression_rate,
                                  chart_labels=chart_labels,
                                  chart_files_data=chart_files_data,
                                  chart_impressions_data=chart_impressions_data,
                                  chart_earnings_data=chart_earnings_data)

@bp.route('/upload')
@require_publisher
async def upload():
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            select(Publisher).where(Publisher.id == session['publisher_id'])
        )
        publisher = result.scalar_one_or_none()
        
    return await render_template('publisher_upload.html', 
                                  active_page='upload',
                                  email=session['publisher_email'],
                                  traffic_source=publisher.traffic_source if publisher else '',
                                  api_key=publisher.api_key if publisher else None)

@bp.route('/api-management')
@require_publisher
async def api_management():
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            select(Publisher).where(Publisher.id == session['publisher_id'])
        )
        publisher = result.scalar_one_or_none()
        
    return await render_template('api_management.html', 
                                  active_page='api',
                                  email=session['publisher_email'],
                                  api_key=publisher.api_key if publisher else None)

@bp.route('/generate-api-key', methods=['POST'])
@require_publisher
async def generate_api_key():
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(Publisher).where(Publisher.id == session['publisher_id'])
            )
            publisher = result.scalar_one_or_none()
            
            if not publisher:
                return jsonify({'status': 'error', 'message': 'Publisher not found'}), 404
            
            new_api_key = token_hex(32)
            publisher.api_key = new_api_key
            await db_session.commit()
            
            return jsonify({'status': 'success', 'api_key': new_api_key}), 200
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Error generating API key: {e}")
            return jsonify({'status': 'error', 'message': 'Failed to generate API key'}), 500

@bp.route('/upload-video', methods=['POST'])
@require_publisher
async def upload_video():
    temp_file = None
    try:
        files = await request.files
        if 'video' not in files:
            return jsonify({'status': 'error', 'message': 'No video file provided'}), 400
        
        video_file = files['video']
        if not video_file.filename:
            return jsonify({'status': 'error', 'message': 'No file selected'}), 400
        
        safe_filename = secure_filename(video_file.filename) or 'video_upload'
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'_{safe_filename}') as temp_file:
            temp_path = temp_file.name
        
        try:
            await video_file.save(temp_path)
            
            file_size = os.path.getsize(temp_path)
            if file_size > 2 * 1024 * 1024 * 1024:
                return jsonify({'status': 'error', 'message': 'File size exceeds 2 GB limit'}), 400
            
            secret_code = token_hex(Telegram.SECRET_CODE_LENGTH)
            
            sent_message = await TelegramBot.send_file(
                entity=Telegram.CHANNEL_ID,
                file=temp_path,
                caption=f'`{secret_code}`'
            )
            if isinstance(sent_message, list):
                sent_message = sent_message[0]
            message_id = sent_message.id
            
            telegram_message = await get_message(message_id=message_id)
            if not telegram_message:
                logger.error(f"Could not retrieve message after upload: {message_id}")
                return jsonify({'status': 'error', 'message': 'Failed to retrieve uploaded file'}), 500
            
            filename, file_size, mime_type = get_file_properties(telegram_message)
            
            video_duration = None
            if hasattr(telegram_message, 'video') and telegram_message.video:
                if hasattr(telegram_message.video, 'attributes'):
                    for attr in telegram_message.video.attributes:
                        duration = getattr(attr, 'duration', None)
                        if duration:
                            video_duration = duration
                            break
            elif hasattr(telegram_message, 'document') and telegram_message.document:
                if hasattr(telegram_message.document, 'attributes'):
                    for attr in telegram_message.document.attributes:
                        duration = getattr(attr, 'duration', None)
                        if duration:
                            video_duration = duration
                            break
            
            async with AsyncSessionLocal() as db_session:
                try:
                    file_record = File(
                        telegram_message_id=message_id,
                        filename=filename,
                        file_size=file_size,
                        mime_type=mime_type,
                        access_code=secret_code,
                        video_duration=int(video_duration) if video_duration else None,
                        publisher_id=session.get('publisher_id')
                    )
                    db_session.add(file_record)
                    await db_session.commit()
                except Exception as e:
                    await db_session.rollback()
                    logger.error(f"Error saving file to database: {e}")
                    return jsonify({'status': 'error', 'message': 'Database error'}), 500
            
            logger.info(f"File uploaded by publisher {session['publisher_email']}: {filename}, hash_id: {secret_code}")
            
            play_link = f'{Server.BASE_URL}/play/{secret_code}'
            
            return jsonify({
                'status': 'success',
                'hash_id': secret_code,
                'play_link': play_link,
                'filename': filename,
                'message': 'Video uploaded successfully'
            }), 200
            
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    logger.warning(f"Could not remove temp file: {e}")
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

@bp.route('/videos')
@require_publisher
async def videos():
    from_date = request.args.get('from_date', '')
    to_date = request.args.get('to_date', '')
    
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            select(Publisher).where(Publisher.id == session['publisher_id'])
        )
        publisher = result.scalar_one_or_none()
        
        query = select(File).where(File.publisher_id == session['publisher_id'])
        
        if from_date:
            try:
                from_datetime = datetime.strptime(from_date, '%Y-%m-%d')
                query = query.where(File.created_at >= from_datetime)
            except ValueError:
                pass
        
        if to_date:
            try:
                to_datetime = datetime.strptime(to_date, '%Y-%m-%d')
                to_datetime = to_datetime.replace(hour=23, minute=59, second=59)
                query = query.where(File.created_at <= to_datetime)
            except ValueError:
                pass
        
        result = await db_session.execute(query.order_by(File.created_at.desc()))
        files = result.scalars().all()
        
        total_files = len(files)
        
        date_counts = {}
        for file in files:
            file_date = file.created_at.date().isoformat()
            date_counts[file_date] = date_counts.get(file_date, 0) + 1
        
        chart_labels = sorted(date_counts.keys())
        chart_data = [date_counts[label] for label in chart_labels]
        
    return await render_template('publisher_videos.html', 
                                  active_page='videos',
                                  email=session['publisher_email'],
                                  files=files,
                                  total_files=total_files,
                                  from_date=from_date,
                                  to_date=to_date,
                                  chart_labels=chart_labels,
                                  chart_data=chart_data)

@bp.route('/delete-video/<int:file_id>', methods=['POST'])
@require_publisher
async def delete_video(file_id):
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(File).where(
                    and_(
                        File.id == file_id,
                        File.publisher_id == session['publisher_id']
                    )
                )
            )
            file = result.scalar_one_or_none()
            
            if not file:
                return jsonify({'status': 'error', 'message': 'File not found or unauthorized'}), 404
            
            await db_session.delete(file)
            await db_session.commit()
            
            logger.info(f"File deleted by publisher {session['publisher_email']}: {file.filename}, hash_id: {file.access_code}")
            
            return jsonify({'status': 'success', 'message': 'Video deleted successfully'}), 200
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Error deleting file: {e}")
            return jsonify({'status': 'error', 'message': 'Failed to delete video'}), 500

@bp.route('/withdraw')
@require_publisher
async def withdraw():
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            select(Publisher).where(Publisher.id == session['publisher_id'])
        )
        publisher = result.scalar_one_or_none()
        
        bank_result = await db_session.execute(
            select(BankAccount).where(
                and_(
                    BankAccount.publisher_id == session['publisher_id'],
                    BankAccount.is_active == True
                )
            ).order_by(BankAccount.created_at.desc())
        )
        bank_account = bank_result.scalar_one_or_none()
        
        withdrawals_result = await db_session.execute(
            select(WithdrawalRequest).where(
                WithdrawalRequest.publisher_id == session['publisher_id']
            ).order_by(WithdrawalRequest.requested_at.desc())
        )
        withdrawals = withdrawals_result.scalars().all()
        
        settings_result = await db_session.execute(select(Settings))
        settings = settings_result.scalar_one_or_none()
        minimum_withdrawal = settings.minimum_withdrawal if settings else 10.0
        
    return await render_template('publisher_withdraw.html',
                                  active_page='withdraw',
                                  email=session['publisher_email'],
                                  balance=publisher.balance if publisher else 0.0,
                                  bank_account=bank_account,
                                  withdrawals=withdrawals,
                                  minimum_withdrawal=minimum_withdrawal,
                                  message=request.args.get('message'))

@bp.route('/save-bank-account', methods=['POST'])
@require_publisher
async def save_bank_account():
    data = await request.form
    
    async with AsyncSessionLocal() as db_session:
        try:
            existing_result = await db_session.execute(
                select(BankAccount).where(
                    and_(
                        BankAccount.publisher_id == session['publisher_id'],
                        BankAccount.is_active == True
                    )
                )
            )
            existing_account = existing_result.scalar_one_or_none()
            
            if existing_account:
                existing_account.account_holder_name = data.get('account_holder_name', '')
                existing_account.bank_name = data.get('bank_name', '')
                existing_account.account_number = data.get('account_number', '')
                existing_account.routing_number = data.get('routing_number', '')
                existing_account.swift_code = data.get('swift_code', '')
                existing_account.country = data.get('country', '')
            else:
                bank_account = BankAccount(
                    publisher_id=session['publisher_id'],
                    account_holder_name=data.get('account_holder_name'),
                    bank_name=data.get('bank_name'),
                    account_number=data.get('account_number'),
                    routing_number=data.get('routing_number'),
                    swift_code=data.get('swift_code'),
                    country=data.get('country')
                )
                db_session.add(bank_account)
            
            await db_session.commit()
            
            logger.info(f"Bank account saved for publisher {session['publisher_email']}")
            
            return redirect('/publisher/withdraw?message=Bank account saved successfully')
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Error saving bank account: {e}")
            return redirect('/publisher/withdraw?message=Failed to save bank account')

@bp.route('/request-withdrawal', methods=['POST'])
@require_publisher
async def request_withdrawal():
    data = await request.form
    amount = float(data.get('amount', 0))
    
    async with AsyncSessionLocal() as db_session:
        try:
            result = await db_session.execute(
                select(Publisher).where(Publisher.id == session['publisher_id'])
            )
            publisher = result.scalar_one_or_none()
            
            bank_result = await db_session.execute(
                select(BankAccount).where(
                    and_(
                        BankAccount.publisher_id == session['publisher_id'],
                        BankAccount.is_active == True
                    )
                )
            )
            bank_account = bank_result.scalar_one_or_none()
            
            if not bank_account:
                return redirect('/publisher/withdraw?message=Please add bank account first')
            
            settings_result = await db_session.execute(select(Settings))
            settings = settings_result.scalar_one_or_none()
            minimum_withdrawal = settings.minimum_withdrawal if settings else 10.0
            
            if not publisher:
                return redirect('/publisher/withdraw?message=Publisher not found')
            
            if amount < minimum_withdrawal:
                return redirect(f'/publisher/withdraw?message=Minimum withdrawal amount is ${minimum_withdrawal}')
            
            if amount > publisher.balance:
                return redirect('/publisher/withdraw?message=Insufficient balance')
            
            publisher.balance -= amount
            
            withdrawal = WithdrawalRequest(
                publisher_id=session['publisher_id'],
                bank_account_id=bank_account.id,
                amount=amount,
                status='pending'
            )
            db_session.add(withdrawal)
            
            await db_session.commit()
            
            logger.info(f"Withdrawal requested by publisher {session['publisher_email']}: ${amount}")
            
            return redirect('/publisher/withdraw?message=Withdrawal request submitted successfully')
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Error requesting withdrawal: {e}")
            return redirect('/publisher/withdraw?message=Failed to submit withdrawal request')
