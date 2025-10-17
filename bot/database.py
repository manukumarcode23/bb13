from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from os import environ
from logging import getLogger
from urllib.parse import urlparse, urlunparse
from dotenv import load_dotenv
from pathlib import Path

# Load .env file to ensure DATABASE_URL is available (don't override existing env vars)
load_dotenv(Path(__file__).parent.parent / '.env')

logger = getLogger('bot.database')

class Base(DeclarativeBase):
    pass

# Create async engine
database_url = environ.get("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL environment variable is required")

# Parse the URL and remove SSL-related parameters that asyncpg doesn't support
parsed_url = urlparse(database_url)
# Remove query parameters like sslmode
clean_url = urlunparse((
    parsed_url.scheme,
    parsed_url.netloc,
    parsed_url.path,
    parsed_url.params,
    '',  # Remove query string
    parsed_url.fragment
))

engine = create_async_engine(
    clean_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={
        "server_settings": {
            "application_name": "telegram_bot",
        }
    }
)

# Create async session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def create_default_admin():
    """Create or update default admin account with current password"""
    from bot.models import Publisher
    import bcrypt
    
    # Use default values if env vars are not set or empty
    default_admin_email = environ.get("ADMIN_EMAIL") or "admin@bot.com"
    default_admin_password = environ.get("ADMIN_PASSWORD") or "admin123"
    
    async with AsyncSessionLocal() as session:
        try:
            from sqlalchemy import select
            
            result = await session.execute(
                select(Publisher).where(Publisher.email == default_admin_email)
            )
            existing_admin = result.scalar_one_or_none()
            
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(default_admin_password.encode('utf-8'), salt).decode('utf-8')
            
            if not existing_admin:
                admin = Publisher(
                    email=default_admin_email,
                    password_hash=password_hash,
                    traffic_source="System Admin",
                    is_admin=True,
                    is_active=True
                )
                
                session.add(admin)
                await session.commit()
                logger.info(f"Default admin account created: {default_admin_email}")
            else:
                existing_admin.password_hash = password_hash
                existing_admin.is_admin = True
                existing_admin.is_active = True
                await session.commit()
                logger.info(f"Admin account password updated: {default_admin_email}")
                
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating/updating default admin: {e}")

async def run_migrations():
    """Run database migrations for schema changes"""
    from sqlalchemy import text
    
    async with engine.begin() as conn:
        try:
            # Add android_package_name column if it doesn't exist
            await conn.execute(text(
                "ALTER TABLE settings ADD COLUMN IF NOT EXISTS android_package_name VARCHAR(255)"
            ))
            # Add android_deep_link_scheme column if it doesn't exist
            await conn.execute(text(
                "ALTER TABLE settings ADD COLUMN IF NOT EXISTS android_deep_link_scheme VARCHAR(100)"
            ))
            # Add minimum_withdrawal column if it doesn't exist
            await conn.execute(text(
                "ALTER TABLE settings ADD COLUMN IF NOT EXISTS minimum_withdrawal FLOAT DEFAULT 10.0"
            ))
            # Add balance column to publishers table if it doesn't exist
            await conn.execute(text(
                "ALTER TABLE publishers ADD COLUMN IF NOT EXISTS balance FLOAT DEFAULT 0.0"
            ))
            # Add ads_api_token column to settings if it doesn't exist
            await conn.execute(text(
                "ALTER TABLE settings ADD COLUMN IF NOT EXISTS ads_api_token TEXT"
            ))
            # Add callback_mode column to settings if it doesn't exist
            await conn.execute(text(
                "ALTER TABLE settings ADD COLUMN IF NOT EXISTS callback_mode VARCHAR(10) DEFAULT 'POST'"
            ))
            # Add callback_method column to link_transactions if it doesn't exist
            await conn.execute(text(
                "ALTER TABLE link_transactions ADD COLUMN IF NOT EXISTS callback_method VARCHAR(10)"
            ))
            
            # Create bank_accounts table if it doesn't exist
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS bank_accounts (
                    id SERIAL PRIMARY KEY,
                    publisher_id INTEGER NOT NULL,
                    account_holder_name VARCHAR(255) NOT NULL,
                    bank_name VARCHAR(255) NOT NULL,
                    account_number VARCHAR(100) NOT NULL,
                    routing_number VARCHAR(50),
                    swift_code VARCHAR(50),
                    country VARCHAR(100) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create withdrawal_requests table if it doesn't exist
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS withdrawal_requests (
                    id SERIAL PRIMARY KEY,
                    publisher_id INTEGER NOT NULL,
                    bank_account_id INTEGER NOT NULL,
                    amount FLOAT NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    admin_note TEXT,
                    requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP WITH TIME ZONE
                )
            """))
            
            # Create indexes for better query performance
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_bank_accounts_publisher_id ON bank_accounts(publisher_id)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_publisher_id ON withdrawal_requests(publisher_id)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_bank_account_id ON withdrawal_requests(bank_account_id)"
            ))
            
            logger.info("Database migrations completed successfully")
        except Exception as e:
            logger.error(f"Error running migrations: {e}")

async def init_db():
    """Initialize database tables"""
    # Import models to ensure they are registered
    from bot import models  # noqa: F401
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully")
    
    await run_migrations()
    await create_default_admin()

async def get_db_session():
    """Get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def close_db():
    """Close database connection"""
    await engine.dispose()
    logger.info("Database connection closed")