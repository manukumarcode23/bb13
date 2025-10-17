from importlib import import_module
from pathlib import Path
from bot import TelegramBot, logger
from bot.config import Telegram
from bot.server import server
import asyncio
from datetime import datetime, timedelta
from bot.database import AsyncSessionLocal
from bot.models import AdPlayCount
from sqlalchemy import delete

def load_plugins():
    count = 0
    for path in Path('bot/plugins').rglob('*.py'):
        import_module(f'bot.plugins.{path.stem}')
        count += 1
    logger.info(f'Loaded {count} {"plugins" if count > 1 else "plugin"}.')

async def cleanup_old_play_counts():
    """Background task to clean up old ad play count records every 24 hours"""
    while True:
        try:
            await asyncio.sleep(86400)
            
            cutoff_date = datetime.now().date() - timedelta(days=7)
            
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    delete(AdPlayCount).where(AdPlayCount.play_date < cutoff_date)
                )
                deleted_count = result.rowcount
                await session.commit()
                
                if deleted_count > 0:
                    logger.info(f'Cleaned up {deleted_count} old ad play count records older than 7 days')
        except Exception as e:
            logger.error(f'Error in cleanup task: {e}')

if __name__ == '__main__':
    logger.info('initializing...')
    TelegramBot.loop.create_task(server.serve())
    TelegramBot.loop.create_task(cleanup_old_play_counts())
    TelegramBot.start(bot_token=Telegram.BOT_TOKEN)
    logger.info('Telegram client is now started.')
    logger.info('Loading bot plugins...')
    load_plugins()
    logger.info('Bot is now ready!')
    TelegramBot.run_until_disconnected()