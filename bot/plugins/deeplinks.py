from telethon.events import NewMessage
from telethon.tl.custom import Message
from bot import TelegramBot
from bot.modules.decorators import verify_user
from bot.modules.telegram import get_message
from bot.modules.static import *
from bot.database import AsyncSessionLocal
from bot.models import User

async def save_user_to_db(user_id: int, username: str, first_name: str, last_name: str):
    """Save user information to database"""
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        try:
            # Check if user already exists by telegram_id
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            existing_user = result.scalar_one_or_none()
            
            if not existing_user:
                user_record = User(
                    telegram_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    is_allowed=True
                )
                session.add(user_record)
            else:
                # Update existing user info
                existing_user.username = username
                existing_user.first_name = first_name
                existing_user.last_name = last_name
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"Error saving user to database: {e}")

