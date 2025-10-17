from quart import Blueprint, Response, request, render_template, redirect, jsonify
from .error import abort
from bot import TelegramBot
from bot.config import Telegram, Server
from math import ceil, floor
from bot.modules.telegram import get_message, get_file_properties
from bot.database import AsyncSessionLocal
from bot.models import AccessLog, File, LinkTransaction, PublisherImpression, Settings, Publisher
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from secrets import token_hex
import httpx
import logging
import os
from pathlib import Path
import tempfile
from werkzeug.utils import secure_filename

bp = Blueprint('main', __name__)
logger = logging.getLogger('bot.server')

async def send_links_to_api(android_id: str, stream_link: str, download_link: str, callback_url: str, callback_method: str = 'POST') -> tuple[bool, int, str]:
    """Send generated links to external API using GET or POST method"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if callback_method.upper() == 'GET':
                params = {
                    'android_id': android_id,
                    'stream_link': stream_link,
                    'download_link': download_link
                }
                response = await client.get(callback_url, params=params)
            else:
                payload = {
                    'android_id': android_id,
                    'stream_link': stream_link,
                    'download_link': download_link
                }
                response = await client.post(callback_url, json=payload)
            
            success = 200 <= response.status_code < 300
            if not success:
                logger.warning(f"API callback ({callback_method}) failed with status {response.status_code}: {response.text}")
            return success, response.status_code, response.text
    except Exception as e:
        logger.error(f"Error sending links to API via {callback_method}: {e}")
        return False, 0, str(e)

async def log_access_attempt(file_id: int, user_ip: str, user_agent: str, success: bool):
    """Log file access attempt to database"""
    async with AsyncSessionLocal() as session:
        try:
            access_log = AccessLog(
                file_id=file_id,
                user_ip=user_ip,
                user_agent=user_agent or '',
                success=success
            )
            session.add(access_log)
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"Error logging access attempt: {e}")

@bp.route('/')
async def home():
    return await render_template('index.html', bot_username=Telegram.BOT_USERNAME)

@bp.route('/upload', methods=['GET'])
async def upload_page():
    return await render_template('upload.html')

@bp.route('/upload', methods=['POST'])
async def handle_upload():
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
                        if hasattr(attr, 'duration'):
                            video_duration = attr.duration
                            break
            elif hasattr(telegram_message, 'document') and telegram_message.document:
                if hasattr(telegram_message.document, 'attributes'):
                    for attr in telegram_message.document.attributes:
                        if hasattr(attr, 'duration'):
                            video_duration = attr.duration
                            break
            
            async with AsyncSessionLocal() as session:
                try:
                    file_record = File(
                        telegram_message_id=message_id,
                        filename=filename,
                        file_size=file_size,
                        mime_type=mime_type,
                        access_code=secret_code,
                        video_duration=int(video_duration) if video_duration else None
                    )
                    session.add(file_record)
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Error saving file to database: {e}")
                    return jsonify({'status': 'error', 'message': 'Database error'}), 500
            
            logger.info(f"File uploaded via web: {filename}, hash_id: {secret_code}")
            
            play_link = f'{Server.BASE_URL}/play/{secret_code}'
            
            return jsonify({
                'status': 'success',
                'hash_id': secret_code,
                'play_link': play_link,
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

@bp.route('/api/request', methods=['POST'])
async def request_links():
    data = await request.get_json()
    android_id = data.get('android_id')
    hash_id = data.get('hash_id')
    
    if not android_id or not hash_id:
        return jsonify({'status': 'error', 'message': 'android_id and hash_id are required'}), 400
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(File).where(File.access_code == hash_id)
        )
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
        
        if not file_record.is_active:
            return jsonify({'status': 'error', 'message': 'File has been revoked'}), 403
        
        if file_record.requested_by_android_id and file_record.requested_by_android_id != android_id:
            return jsonify({'status': 'error', 'message': 'File has already been requested by another user'}), 409
        
        file_record.requested_by_android_id = android_id
        await session.commit()
    
    return jsonify({
        'status': 'pending',
        'message': 'Please wait, links are being generated. Use the postback URL to generate the links.'
    }), 202

@bp.route('/api/postback', methods=['GET', 'POST'])
async def postback_generate_links():
    if request.method == 'GET':
        android_id = request.args.get('android_id')
        hash_id = request.args.get('hash_id')
        callback_url = request.args.get('callback_url')
        callback_method = request.args.get('callback_method')
    else:
        data = await request.get_json()
        android_id = data.get('android_id')
        hash_id = data.get('hash_id')
        callback_url = data.get('callback_url')
        callback_method = data.get('callback_method')
    
    if not android_id or not hash_id:
        return jsonify({'status': 'error', 'message': 'android_id and hash_id are required'}), 400
    
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(File).where(File.access_code == hash_id)
            )
            file_record = result.scalar_one_or_none()
            
            if not file_record:
                return jsonify({'status': 'error', 'message': 'File not found'}), 404
            
            if not file_record.is_active:
                return jsonify({'status': 'error', 'message': 'File has been revoked'}), 403
            
            if file_record.requested_by_android_id != android_id:
                return jsonify({'status': 'error', 'message': 'Android ID does not match the request'}), 403
            
            settings_result = await session.execute(select(Settings))
            settings = settings_result.scalar_one_or_none()
            
            default_callback_mode = settings.callback_mode if settings and settings.callback_mode else 'POST'
            final_callback_method = callback_method if callback_method else default_callback_mode
            
            stream_token = token_hex(32)
            download_token = token_hex(32)
            
            if file_record.video_duration:
                expiry_seconds = file_record.video_duration + 3600
            else:
                expiry_seconds = 7200
            
            expiry_time = datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds)
            
            file_record.temporary_stream_token = stream_token
            file_record.temporary_download_token = download_token
            file_record.link_expiry_time = expiry_time
            
            stream_link = f'{Server.BASE_URL}/stream/{file_record.telegram_message_id}?token={stream_token}'
            download_link = f'{Server.BASE_URL}/dl/{file_record.telegram_message_id}?token={download_token}'
            
            callback_status = None
            callback_response = None
            delivered = True
            
            if callback_url:
                success, status_code, response_text = await send_links_to_api(
                    android_id=android_id,
                    stream_link=stream_link,
                    download_link=download_link,
                    callback_url=callback_url,
                    callback_method=final_callback_method
                )
                callback_status = status_code
                callback_response = response_text
                delivered = success
            
            transaction = LinkTransaction(
                file_id=file_record.telegram_message_id,
                android_id=android_id,
                hash_id=hash_id,
                stream_link=stream_link,
                download_link=download_link,
                callback_url=callback_url,
                callback_method=final_callback_method if callback_url else None,
                callback_status=callback_status,
                callback_response=callback_response,
                delivered=delivered
            )
            session.add(transaction)
            
            await session.commit()
            
            logger.info(f"Links generated for android_id: {android_id}, hash_id: {hash_id}, callback: {callback_url}, method: {final_callback_method if callback_url else 'N/A'}")
            
            response_data = {
                'status': 'success',
                'message': 'Links generated successfully. Use /api/links endpoint to retrieve them.'
            }
            
            if callback_url and delivered:
                response_data['callback_delivered'] = True
            elif callback_url and not delivered:
                response_data['callback_delivered'] = False
                response_data['callback_error'] = callback_response
            
            return jsonify(response_data), 200
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error generating links: {e}")
            return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

@bp.route('/api/links', methods=['POST'])
async def get_links_by_android_id():
    data = await request.get_json()
    android_id = data.get('android_id')
    hash_id = data.get('hash_id')
    
    if not android_id or not hash_id:
        return jsonify({'status': 'error', 'message': 'android_id and hash_id are required'}), 400
    
    async with AsyncSessionLocal() as session:
        file_result = await session.execute(
            select(File).where(File.access_code == hash_id)
        )
        file_record = file_result.scalar_one_or_none()
        
        if not file_record:
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
        
        if not file_record.is_active:
            return jsonify({'status': 'error', 'message': 'File has been revoked'}), 403
        
        if file_record.requested_by_android_id != android_id:
            return jsonify({'status': 'error', 'message': 'Android ID does not match'}), 403
        
        if not file_record.temporary_stream_token or not file_record.temporary_download_token:
            return jsonify({'status': 'error', 'message': 'No links have been generated yet. Call /api/postback first.'}), 404
        
        if not file_record.link_expiry_time or datetime.now(timezone.utc) > file_record.link_expiry_time:
            return jsonify({'status': 'error', 'message': 'Links have expired'}), 403
        
        stream_link = f'{Server.BASE_URL}/stream/{file_record.telegram_message_id}?token={file_record.temporary_stream_token}'
        download_link = f'{Server.BASE_URL}/dl/{file_record.telegram_message_id}?token={file_record.temporary_download_token}'
        
        return jsonify({
            'status': 'success',
            'android_id': android_id,
            'hash_id': hash_id,
            'stream_link': stream_link,
            'download_link': download_link,
            'expires_at': file_record.link_expiry_time.isoformat()
        }), 200

@bp.route('/api/tracking/postback', methods=['GET'])
async def tracking_postback():
    hash_id = request.args.get('hash_id')
    android_id = request.args.get('android_id')
    
    if not hash_id or not android_id:
        return jsonify({
            'status': 'error',
            'message': 'hash_id and android_id are required'
        }), 400
    
    user_ip = request.remote_addr
    
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(File).where(File.access_code == hash_id)
            )
            file_record = result.scalar_one_or_none()
            
            if not file_record:
                return jsonify({
                    'status': 'error',
                    'message': 'Video not found'
                }), 404
            
            if not file_record.publisher_id:
                return jsonify({
                    'status': 'error',
                    'message': 'No publisher associated with this video'
                }), 400
            
            impression = PublisherImpression(
                publisher_id=file_record.publisher_id,
                hash_id=hash_id,
                android_id=android_id,
                user_ip=user_ip
            )
            session.add(impression)
            
            settings_result = await session.execute(select(Settings))
            settings = settings_result.scalar_one_or_none()
            impression_rate = settings.impression_rate if settings else 0.0
            
            publisher_result = await session.execute(
                select(Publisher).where(Publisher.id == file_record.publisher_id)
            )
            publisher = publisher_result.scalar_one_or_none()
            
            if publisher:
                publisher.balance += impression_rate
            
            await session.commit()
            
            logger.info(f"Impression tracked for publisher {file_record.publisher_id}, hash_id: {hash_id}, android_id: {android_id}, earned: ${impression_rate}")
            
            return jsonify({
                'status': 'success',
                'message': 'Impression tracked successfully',
                'publisher_id': file_record.publisher_id,
                'hash_id': hash_id
            }), 200
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error tracking impression: {e}")
            return jsonify({
                'status': 'error',
                'message': 'Internal server error'
            }), 500

@bp.route('/dl/<int:file_id>')
async def transmit_file(file_id):
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent')
    
    file = await get_message(message_id=int(file_id))
    if not file:
        await log_access_attempt(file_id, user_ip or '', user_agent or '', False)
        abort(404)
    
    token = request.args.get('token')
    
    if not token:
        await log_access_attempt(file_id, user_ip or '', user_agent or '', False)
        abort(401, 'Token is required')
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(File).where(File.telegram_message_id == file_id)
        )
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            await log_access_attempt(file_id, user_ip or '', user_agent or '', False)
            abort(404)
        
        if file_record.temporary_download_token != token:
            await log_access_attempt(file_id, user_ip or '', user_agent or '', False)
            abort(403)
        
        if not file_record.link_expiry_time or datetime.now(timezone.utc) > file_record.link_expiry_time:
            await log_access_attempt(file_id, user_ip or '', user_agent or '', False)
            abort(403, 'Link has expired')
        
        if not file_record.is_active:
            await log_access_attempt(file_id, user_ip or '', user_agent or '', False)
            abort(403, 'File has been revoked')
        
    range_header = request.headers.get('Range')
    
    # Log successful access attempt
    await log_access_attempt(file_id, user_ip or '', user_agent or '', True)

    file_name, file_size, mime_type = get_file_properties(file)
    
    if range_header:
        from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes = 0
        until_bytes = file_size - 1

    if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        abort(416, 'Invalid range.')

    chunk_size = 1024 * 1024
    until_bytes = min(until_bytes, file_size - 1)

    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = until_bytes % chunk_size + 1

    req_length = until_bytes - from_bytes + 1
    part_count = ceil(until_bytes / chunk_size) - floor(offset / chunk_size)
    
    headers = {
            "Content-Type": f"{mime_type}",
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(req_length),
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Accept-Ranges": "bytes",
        }

    async def file_generator():
        current_part = 1
        # Type hint to help LSP understand that file is valid for iter_download
        async for chunk in TelegramBot.iter_download(file, offset=offset, chunk_size=chunk_size, stride=chunk_size, file_size=file_size):  # type: ignore
            if not chunk:
                break
            elif part_count == 1:
                yield chunk[first_part_cut:last_part_cut]
            elif current_part == 1:
                yield chunk[first_part_cut:]
            elif current_part == part_count:
                yield chunk[:last_part_cut]
            else:
                yield chunk

            current_part += 1

            if current_part > part_count:
                break

    return Response(file_generator(), headers=headers, status=206 if range_header else 200)

@bp.route('/stream/<int:file_id>')
async def stream_file(file_id):
    token = request.args.get('token')
    
    if not token:
        abort(401, 'Token is required')
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(File).where(File.telegram_message_id == file_id)
        )
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            abort(404)
        
        if file_record.temporary_stream_token != token:
            abort(403)
        
        if not file_record.link_expiry_time or datetime.now(timezone.utc) > file_record.link_expiry_time:
            abort(403, 'Link has expired')
        
        if not file_record.is_active:
            abort(403, 'File has been revoked')
        
        download_token = file_record.temporary_download_token
    
    return await render_template('player.html', mediaLink=f'{Server.BASE_URL}/dl/{file_id}?token={download_token}')

@bp.route('/play/<hash_id>')
async def play_video(hash_id):
    async with AsyncSessionLocal() as session:
        file_result = await session.execute(
            select(File).where(File.access_code == hash_id)
        )
        file_record = file_result.scalar_one_or_none()
        
        if not file_record:
            abort(404, 'Video not found')
        
        if not file_record.is_active:
            abort(403, 'This video has been removed')
        
        settings_result = await session.execute(select(Settings))
        settings = settings_result.scalar_one_or_none()
        
        package_name = settings.android_package_name if settings and settings.android_package_name else ''
        deep_link_scheme = settings.android_deep_link_scheme if settings and settings.android_deep_link_scheme else ''
    
    return await render_template('play.html', 
                                hash_id=hash_id, 
                                package_name=package_name, 
                                deep_link_scheme=deep_link_scheme,
                                filename=file_record.filename)

@bp.route('/terms-of-service')
async def terms_of_service():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Settings))
        settings = result.scalar_one_or_none()
        
        terms = settings.terms_of_service if settings else 'Terms of Service not available.'
    
    return await render_template('terms.html', content=terms, title='Terms of Service')

@bp.route('/privacy-policy')
async def privacy_policy():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Settings))
        settings = result.scalar_one_or_none()
        
        privacy = settings.privacy_policy if settings else 'Privacy Policy not available.'
    
    return await render_template('privacy.html', content=privacy, title='Privacy Policy')