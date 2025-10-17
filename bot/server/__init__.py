from quart import Quart, make_response
from uvicorn import Server as UvicornServer, Config
from logging import getLogger
from bot.config import Server, LOGGER_CONFIG_JSON
from bot.database import init_db, close_db
from secrets import token_hex

from . import main, error, auth, admin, publisher, ad_api

logger = getLogger('uvicorn')
instance = Quart(__name__)
instance.config['RESPONSE_TIMEOUT'] = None
instance.config['REQUEST_TIMEOUT'] = None
instance.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024
instance.config['SECRET_KEY'] = token_hex(32)

@instance.before_serving
async def before_serve():
    await init_db()
    logger.info('Web server is started!')
    logger.info(f'Server running on {Server.BIND_ADDRESS}:{Server.PORT}')

@instance.after_serving
async def after_serve():
    await close_db()
    logger.info('Web server is shutting down!')

instance.register_blueprint(main.bp)
instance.register_blueprint(auth.bp)
instance.register_blueprint(admin.bp)
instance.register_blueprint(publisher.bp)
instance.register_blueprint(ad_api.bp)

@instance.errorhandler(400)
async def handle_invalid_request(e):
    return await make_response('Invalid request.', 400)

@instance.errorhandler(404)  
async def handle_not_found(e):
    return await make_response('Resource not found.', 404)

@instance.errorhandler(405)
async def handle_invalid_method(e):
    return await make_response('Invalid request method.', 405)

@instance.errorhandler(error.HTTPError)
async def handle_http_error(e):
    error_message = error.error_messages.get(e.status_code)
    return await make_response(e.description or error_message or 'Unknown error', e.status_code)

server = UvicornServer (
    Config (
        app=instance,
        host=Server.BIND_ADDRESS,
        port=Server.PORT,
        log_config=LOGGER_CONFIG_JSON,
        timeout_keep_alive=300,
        timeout_graceful_shutdown=30
    )
)