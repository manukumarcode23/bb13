from telethon import Button
from telethon.events import NewMessage
from telethon.tl.custom import Message
from secrets import token_hex
from bot import TelegramBot
from bot.config import Telegram, Server
from bot.modules.decorators import verify_user
from bot.modules.telegram import send_file_with_caption, filter_files
from bot.modules.static import *
from bot.database import AsyncSessionLocal
from bot.models import File, User, Publisher
from sqlalchemy import select
import asyncio

async def save_file_to_db(message_id: int, filename: str, file_size: int, mime_type: str, access_code: str, video_duration = None, publisher_id = None):
    """Save file information to database"""
    async with AsyncSessionLocal() as session:
        try:
            file_record = File(
                telegram_message_id=message_id,
                filename=filename,
                file_size=file_size,
                mime_type=mime_type,
                access_code=access_code,
                video_duration=int(video_duration) if video_duration else None,
                publisher_id=publisher_id
            )
            session.add(file_record)
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"Error saving file to database: {e}")

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

@TelegramBot.on(NewMessage(incoming=True, func=filter_files))
@verify_user(private=True)
async def user_file_handler(event: NewMessage.Event | Message):
    publisher_id = None
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Publisher).where(Publisher.telegram_id == event.sender.id)
        )
        publisher = result.scalar_one_or_none()
        
        if not publisher or not publisher.is_active:
            await event.reply(
                "❌ **Access Denied**\n\n"
                "Only publishers can upload files through this bot.\n\n"
                "If you are a publisher:\n"
                "1. Get your API key from the publisher dashboard\n"
                "2. Use the /setapikey command to link your account"
            )
            return
        
        if not publisher.api_key:
            await event.reply(
                "❌ **No API Key Found**\n\n"
                "Please generate an API key from the publisher dashboard first, "
                "then link it using /setapikey command."
            )
            return
        
        publisher_id = publisher.id
    
    await save_user_to_db(
        user_id=event.sender.id,
        username=getattr(event.sender, 'username', None),
        first_name=getattr(event.sender, 'first_name', None),
        last_name=getattr(event.sender, 'last_name', None)
    )
    
    secret_code = token_hex(Telegram.SECRET_CODE_LENGTH)
    message = await send_file_with_caption(event.message, f'`{secret_code}`')
    message_id = message.id

    # Get file properties for database
    filename = 'Unknown'
    video_duration = None
    if hasattr(event, 'file') and event.file and event.file.name:
        filename = event.file.name
    elif event.document and event.document.attributes:
        for attr in event.document.attributes:
            if hasattr(attr, 'file_name'):
                filename = attr.file_name
                break
            if hasattr(attr, 'duration'):
                video_duration = attr.duration
    elif event.video:
        filename = 'Video_File'
        if hasattr(event.video, 'attributes'):
            for attr in event.video.attributes:
                if hasattr(attr, 'duration'):
                    video_duration = attr.duration
                    break
    
    file_size = getattr(event.document, 'size', 0) if event.document else (getattr(event.video, 'size', 0) if event.video else 0)
    mime_type = getattr(event.document, 'mime_type', 'application/octet-stream') if event.document else (getattr(event.video, 'mime_type', 'video/mp4') if event.video else 'media/unknown')

    # Save file to database
    await save_file_to_db(
        message_id=message_id,
        filename=filename,
        file_size=file_size,
        mime_type=mime_type,
        access_code=secret_code,
        video_duration=video_duration,
        publisher_id=publisher_id
    )

    file_link = f'{Server.BASE_URL}/play/{secret_code}'
    
    await event.reply(
        message=f'**File uploaded successfully!**\n\n'
                f'**Hash ID:** `{secret_code}`\n'
                f'**Play Link:** {file_link}\n\n'
                f'Click the link to open the video in your app.',
        buttons=[
            [
                Button.inline('Revoke', f'rm_{message_id}_{secret_code}')
            ]
        ]
    )

