from __future__ import annotations

import asyncio
import contextlib
import logging
import selectors
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.callback_answer import CallbackAnswerMiddleware

from app.config import load_config
from app.db import Storage
from app.handlers import admin, common, system, user
from app.services.ai_writer import AiWriter
from app.services.postgres_auth import PostgresAuth
from app.services.pg_sync import PgSync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config()
    storage = Storage(config.database_path)
    ai_writer = AiWriter(config.google_api_key, config.google_model, groq_api_key=config.groq_api_key)
    pg_auth = PostgresAuth(config.postgres_dsn)
    pg_sync = PgSync(config.postgres_dsn)
    pg_sync.ensure_tables()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.callback_query.middleware(CallbackAnswerMiddleware())

    for admin_id in config.admin_ids:
        storage.upsert_admin(admin_id)
    for external in pg_auth.fetch_admins():
        storage.upsert_admin(external.telegram_id, external.full_name, external.username, external.role)
    if config.moderator_chat_id and not storage.get_moderator_chat_id():
        storage.set_moderator_chat_id(config.moderator_chat_id)

    dp.include_router(system.router)
    dp.include_router(common.router)
    dp.include_router(user.router)
    dp.include_router(admin.router)

    async def inject_dependencies(handler, event, data):
        data["storage"] = storage
        data["config"] = config
        data["ai_writer"] = ai_writer
        data["pg_auth"] = pg_auth
        data["pg_sync"] = pg_sync
        return await handler(event, data)

    dp.update.middleware(inject_dependencies)

    # Синхронизируем шаблоны с веб-портала в SQLite при старте
    await pg_sync.sync_templates_to_sqlite(storage)

    web_sync_task = asyncio.create_task(pg_sync.web_queue_loop(bot, storage))

    try:
        await dp.start_polling(bot)
    finally:
        web_sync_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await web_sync_task


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
