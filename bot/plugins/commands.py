from telethon import Button
from telethon.events import NewMessage
from telethon.tl.custom.message import Message
from bot import TelegramBot
from bot.config import Telegram
from bot.modules.static import *
from bot.modules.decorators import verify_user
from bot.database import AsyncSessionLocal
from bot.models import User, Publisher
from sqlalchemy import select

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

@TelegramBot.on(NewMessage(incoming=True, pattern=r'^/start$'))
@verify_user(private=True)
async def welcome(event: NewMessage.Event | Message):
    # Save user to database
    await save_user_to_db(
        user_id=event.sender.id,
        username=getattr(event.sender, 'username', None),
        first_name=getattr(event.sender, 'first_name', None),
        last_name=getattr(event.sender, 'last_name', None)
    )
    await event.reply(
        message=WelcomeText % {'first_name': event.sender.first_name}
    )

@TelegramBot.on(NewMessage(incoming=True, pattern=r'^/setapikey'))
@verify_user(private=True)
async def set_api_key(event: NewMessage.Event | Message):
    try:
        command_parts = event.message.text.split(maxsplit=1)
        
        if len(command_parts) < 2:
            await event.reply(
                "**How to link your API key:**\n\n"
                "Usage: `/setapikey YOUR_API_KEY`\n\n"
                "Example: `/setapikey abc123def456...`\n\n"
                "Get your API key from the publisher dashboard."
            )
            return
        
        api_key = command_parts[1].strip()
        
        if len(api_key) < 10:
            await event.reply("❌ Invalid API key format. Please check and try again.")
            return
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Publisher).where(Publisher.api_key == api_key)
            )
            publisher = result.scalar_one_or_none()
            
            if not publisher:
                await event.reply(
                    "❌ **Invalid API Key**\n\n"
                    "This API key doesn't exist. Please:\n"
                    "1. Login to the publisher dashboard\n"
                    "2. Generate or copy your API key\n"
                    "3. Try again with the correct key"
                )
                return
            
            if not publisher.is_active:
                await event.reply("❌ Your publisher account is inactive. Please contact support.")
                return
            
            if publisher.telegram_id and publisher.telegram_id != event.sender.id:
                await event.reply(
                    "❌ This API key is already linked to another Telegram account."
                )
                return
            
            publisher.telegram_id = event.sender.id
            await session.commit()
            
            await event.reply(
                "✅ **API Key Linked Successfully!**\n\n"
                f"Your publisher account ({publisher.email}) is now connected to this Telegram account.\n\n"
                "You can now upload files directly through this bot!"
            )
            
    except Exception as e:
        print(f"Error in set_api_key: {e}")
        await event.reply("❌ An error occurred. Please try again later.")

@TelegramBot.on(NewMessage(incoming=True, pattern=r'^/myaccount$'))
@verify_user(private=True)
async def my_account(event: NewMessage.Event | Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Publisher).where(Publisher.telegram_id == event.sender.id)
        )
        publisher = result.scalar_one_or_none()
        
        if not publisher:
            await event.reply(
                "**No Publisher Account Linked**\n\n"
                "Use /setapikey to link your publisher account."
            )
            return
        
        api_key_status = "✅ Active" if publisher.api_key else "❌ Not Generated"
        account_status = "✅ Active" if publisher.is_active else "❌ Inactive"
        
        await event.reply(
            f"**Your Publisher Account**\n\n"
            f"📧 Email: {publisher.email}\n"
            f"🔑 API Key: {api_key_status}\n"
            f"📊 Status: {account_status}\n"
            f"📅 Joined: {publisher.created_at.strftime('%Y-%m-%d')}"
        )