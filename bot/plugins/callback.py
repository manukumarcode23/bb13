from telethon.events import CallbackQuery
from bot import TelegramBot
from bot.modules.decorators import verify_user
from bot.modules.static import *
from bot.modules.telegram import get_message
from bot.database import AsyncSessionLocal
from bot.models import File
from sqlalchemy import select

async def delete_file_from_db(message_id: int):
    """Delete file record from database"""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(File).where(File.telegram_message_id == message_id)
            )
            file_record = result.scalar_one_or_none()
            if file_record:
                await session.delete(file_record)
                await session.commit()
                print(f"Deleted file record for message {message_id}")
        except Exception as e:
            await session.rollback()
            print(f"Error deleting file from database: {e}")

@TelegramBot.on(CallbackQuery(pattern=r'^rm_'))
@verify_user(private=True)
async def delete_file(event: CallbackQuery.Event):
    query_data = event.query.data.decode().split('_')

    if len(query_data) != 3:
        return await event.answer(InvalidQueryText, alert=True)

    message = await get_message(int(query_data[1]))

    if not message:
        return await event.answer(MessageNotExist, alert=True)
    if query_data[2] != message.raw_text:
        return await event.answer(InvalidQueryText, alert=True)

    await message.delete()
    
    # Also delete from database
    await delete_file_from_db(int(query_data[1]))

    return await event.answer(LinkRevokedText, alert=True)