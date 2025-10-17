from quart import Blueprint, request, jsonify
from bot.database import AsyncSessionLocal
from bot.models import AdNetwork, AdPlayCount, Settings
from sqlalchemy import select, and_, func
from os import environ
from functools import wraps
from datetime import date

bp = Blueprint('ad_api', __name__, url_prefix='/api')

def require_api_token(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        token = request.args.get('token')
        
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(select(Settings))
            settings = result.scalar_one_or_none()
            
            api_token = settings.ads_api_token if settings and settings.ads_api_token else environ.get('AD_API_TOKEN')
        
        if not api_token:
            return jsonify({'status': 'error', 'message': 'API token not configured'}), 500
        
        if not token or token != api_token:
            return jsonify({'status': 'error', 'message': 'Invalid or missing token'}), 401
        
        return await func(*args, **kwargs)
    return wrapper

async def get_or_create_play_count(db_session, ad_network_id: int, ad_type: str, android_id: str | None = None, user_ip: str | None = None):
    """Get or create play count for today"""
    today = date.today()
    
    result = await db_session.execute(
        select(AdPlayCount).where(
            and_(
                AdPlayCount.ad_network_id == ad_network_id,
                AdPlayCount.ad_type == ad_type,
                AdPlayCount.play_date == today,
                AdPlayCount.android_id == android_id if android_id else AdPlayCount.user_ip == user_ip
            )
        )
    )
    play_count = result.scalar_one_or_none()
    
    if not play_count:
        play_count = AdPlayCount(
            ad_network_id=ad_network_id,
            ad_type=ad_type,
            android_id=android_id,
            user_ip=user_ip,
            play_date=today,
            play_count=0
        )
        db_session.add(play_count)
    
    return play_count

async def find_available_ad_network(db_session, ad_type: str, android_id: str | None = None, user_ip: str | None = None):
    """Find the first available ad network based on daily limits and priority - returns (network, play_count)"""
    result = await db_session.execute(
        select(AdNetwork)
        .where(AdNetwork.status == 'active')
        .order_by(AdNetwork.priority)
    )
    ad_networks = result.scalars().all()
    
    today = date.today()
    
    for network in ad_networks:
        # Check if this network has the requested ad type
        if ad_type == 'banner' and not network.banner_id:
            continue
        elif ad_type == 'interstitial' and not network.interstitial_id:
            continue
        elif ad_type == 'rewarded' and not network.rewarded_id:
            continue
        
        # Get daily limit for this ad type
        if ad_type == 'banner':
            daily_limit = network.banner_daily_limit
        elif ad_type == 'interstitial':
            daily_limit = network.interstitial_daily_limit
        else:  # rewarded
            daily_limit = network.rewarded_daily_limit
        
        # If limit is 0, it means unlimited
        if daily_limit == 0:
            play_count = await get_or_create_play_count(db_session, network.id, ad_type, android_id, user_ip)
            return (network, play_count)
        
        # Check current play count for today
        play_count = await get_or_create_play_count(db_session, network.id, ad_type, android_id, user_ip)
        
        # If under the limit, return this network and play count record
        if play_count.play_count < daily_limit:
            return (network, play_count)
    
    return (None, None)

@bp.route('/banner_ads')
@require_api_token
async def get_banner_ads():
    android_id = request.args.get('android_id')
    user_ip = request.remote_addr
    
    async with AsyncSessionLocal() as db_session:
        # Find available ad network based on daily limits
        network, play_count = await find_available_ad_network(db_session, 'banner', android_id, user_ip)
        
        if not network:
            return jsonify({
                'status': 'error',
                'message': 'No available ad networks. Daily limits reached for all networks.'
            }), 404
        
        # Increment play count using the same record we retrieved
        play_count.play_count += 1
        await db_session.commit()
        
        return jsonify({
            'status': 'success',
            'type': 'banner',
            'network': network.network_name,
            'banner_id': network.banner_id,
            'priority': network.priority
        }), 200

@bp.route('/interstitial_ads')
@require_api_token
async def get_interstitial_ads():
    android_id = request.args.get('android_id')
    user_ip = request.remote_addr
    
    async with AsyncSessionLocal() as db_session:
        # Find available ad network based on daily limits
        network, play_count = await find_available_ad_network(db_session, 'interstitial', android_id, user_ip)
        
        if not network:
            return jsonify({
                'status': 'error',
                'message': 'No available ad networks. Daily limits reached for all networks.'
            }), 404
        
        # Increment play count using the same record we retrieved
        play_count.play_count += 1
        await db_session.commit()
        
        return jsonify({
            'status': 'success',
            'type': 'interstitial',
            'network': network.network_name,
            'interstitial_id': network.interstitial_id,
            'priority': network.priority
        }), 200

@bp.route('/rewarded_ads')
@require_api_token
async def get_rewarded_ads():
    android_id = request.args.get('android_id')
    user_ip = request.remote_addr
    
    async with AsyncSessionLocal() as db_session:
        # Find available ad network based on daily limits
        network, play_count = await find_available_ad_network(db_session, 'rewarded', android_id, user_ip)
        
        if not network:
            return jsonify({
                'status': 'error',
                'message': 'No available ad networks. Daily limits reached for all networks.'
            }), 404
        
        # Increment play count using the same record we retrieved
        play_count.play_count += 1
        await db_session.commit()
        
        return jsonify({
            'status': 'success',
            'type': 'rewarded',
            'network': network.network_name,
            'rewarded_id': network.rewarded_id,
            'priority': network.priority
        }), 200
