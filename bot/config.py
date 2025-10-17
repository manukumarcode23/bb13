from os import environ as env
from dotenv import load_dotenv
from pathlib import Path

# Load .env file from the project root
# Preserve critical environment variables that should not be overridden by .env
_preserved_vars = {
    "DATABASE_URL": env.get("DATABASE_URL"),
    "PGHOST": env.get("PGHOST"),
    "PGPORT": env.get("PGPORT"),
    "PGUSER": env.get("PGUSER"),
    "PGPASSWORD": env.get("PGPASSWORD"),
    "PGDATABASE": env.get("PGDATABASE"),
}

# Load .env file if it exists (but don't override Replit Secrets)
_env_path = Path(__file__).parent.parent / '.env'
if _env_path.exists():
    load_dotenv(_env_path, override=False)
    
    # Restore preserved variables if they were overridden with empty values
    for key, value in _preserved_vars.items():
        if value and not env.get(key):
            env[key] = value

# REQUIRED CONFIGURATION
# Add these environment variables:
# - TELEGRAM_API_ID: Your Telegram API ID
# - TELEGRAM_API_HASH: Your Telegram API Hash
# - TELEGRAM_BOT_TOKEN: Your bot token from @BotFather
# - TELEGRAM_CHANNEL_ID: Channel ID for file storage
# - OWNER_ID: Bot owner's Telegram user ID
# - TELEGRAM_BOT_USERNAME: Bot username without @
# - BASE_URL: Public URL of your deployment (e.g., https://yourdomain.com)
# - DATABASE_URL: PostgreSQL database connection string

class Telegram:
    API_ID = int(env.get("TELEGRAM_API_ID") or "25090660")
    API_HASH = env.get("TELEGRAM_API_HASH") or "58fd3b352d60d49f6d145364c6791c1b"
    OWNER_ID = int(env.get("OWNER_ID") or "8391217905")
    ALLOWED_USER_IDS = (env.get("ALLOWED_USER_IDS") or "8391217905").split(",")
    BOT_USERNAME = env.get("TELEGRAM_BOT_USERNAME") or "Euuejejbot"
    BOT_TOKEN = env.get("TELEGRAM_BOT_TOKEN") or "8223552801:AAFkiAmhvFtEHGsW_y1FHp-xzALlRsDL6TA"
    CHANNEL_ID = int(env.get("TELEGRAM_CHANNEL_ID") or "-1002976875407")
    SECRET_CODE_LENGTH = int(env.get("SECRET_CODE_LENGTH") or "12")

class Server:
    BASE_URL = env.get("BASE_URL") or "https://yourdomain.com"
    CALLBACK_API_URL = env.get("CALLBACK_API_URL")
    BIND_ADDRESS = env.get("BIND_ADDRESS") or "0.0.0.0"
    PORT = int(env.get("PORT") or "5000")
# LOGGING CONFIGURATION
LOGGER_CONFIG_JSON = {
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s][%(name)s][%(levelname)s] -> %(message)s',
            'datefmt': '%d/%m/%Y %H:%M:%S'
        },
    },
    'handlers': {
        'file_handler': {
            'class': 'logging.FileHandler',
            'filename': 'event-log.txt',
            'formatter': 'default'
        },
        'stream_handler': {
            'class': 'logging.StreamHandler',
            'formatter': 'default'
        }
    },
    'loggers': {
        'uvicorn': {
            'level': 'INFO',
            'handlers': ['file_handler', 'stream_handler']
        },
        'uvicorn.error': {
            'level': 'WARNING',
            'handlers': ['file_handler', 'stream_handler']
        },
        'bot': {
            'level': 'INFO',
            'handlers': ['file_handler', 'stream_handler']
        }
    }
}