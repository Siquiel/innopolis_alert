"""
Интеграция Python Telegram-бота с веб-порталом.

Добавь этот код в своего бота.

Зависимости:
    pip install psycopg2-binary aiohttp python-dotenv

Переменные окружения (добавь в .env бота):
    DB_HOST=localhost
    DB_PORT=5432
    DB_NAME=authdb
    DB_USER=postgres
    DB_PASSWORD=admin123
    BOT_API_KEY=change_this_secret_key_123   # тот же что в server/.env
    SERVER_URL=http://localhost:3001
"""

import asyncio
import os
import aiohttp
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:3001")
BOT_API_KEY = os.getenv("BOT_API_KEY", "change_this_secret_key_123")

BOT_HEADERS = {"x-api-key": BOT_API_KEY}


# ── Подключение к БД ──────────────────────────────────────────────────────────

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "authdb"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "admin123"),
    )


# ── Логирование отправки в БД (через API сервера) ─────────────────────────────

async def log_message(session, template_id, emergency_type, chat_id, chat_name,
                       message_text, telegram_message_id=None, sent_by="bot"):
    """Записывает отправленное сообщение в общий лог (виден в Excel-отчёте)."""
    await session.post(
        f"{SERVER_URL}/api/bot/log",
        headers=BOT_HEADERS,
        json={
            "template_id": template_id,
            "emergency_type": emergency_type,
            "chat_id": chat_id,
            "chat_name": chat_name,
            "message_text": message_text,
            "telegram_message_id": telegram_message_id,
            "sent_by": sent_by,
        }
    )


# ── Обработка очереди от веб-портала ─────────────────────────────────────────

async def process_send_queue(bot):
    """
    Вызывай эту функцию периодически (например, каждые 5 секунд).
    Она проверяет задания от веб-портала и выполняет рассылку.

    Пример использования с aiogram:
        asyncio.create_task(queue_polling_loop(bot))
    """
    async with aiohttp.ClientSession() as session:
        resp = await session.get(f"{SERVER_URL}/api/bot/queue", headers=BOT_HEADERS)
        if resp.status != 200:
            return
        jobs = await resp.json()

        for job in jobs:
            chat_ids = job.get("chat_ids") or []
            message_text = job["message_text"]
            buttons = job.get("buttons") or []

            # Формируем inline-кнопки если есть
            reply_markup = None
            if buttons:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=b["text"], url=b["url"])]
                    for b in buttons if b.get("text") and b.get("url")
                ])
                reply_markup = kb

            for chat_id in chat_ids:
                if not chat_id:
                    continue
                try:
                    # Отправка с медиафайлом
                    if job.get("media_url"):
                        media_url = SERVER_URL + job["media_url"]
                        if job["media_url"].endswith((".mp4", ".webm")):
                            sent = await bot.send_video(chat_id, media_url, caption=message_text, reply_markup=reply_markup)
                        else:
                            sent = await bot.send_photo(chat_id, media_url, caption=message_text, reply_markup=reply_markup)
                    else:
                        sent = await bot.send_message(chat_id, message_text, reply_markup=reply_markup)

                    # Логируем в БД
                    await log_message(
                        session,
                        template_id=job.get("template_id"),
                        emergency_type=job.get("emergency_type"),
                        chat_id=chat_id,
                        chat_name=str(chat_id),
                        message_text=message_text,
                        telegram_message_id=sent.message_id,
                        sent_by=job.get("sent_by", "web"),
                    )
                except Exception as e:
                    print(f"Ошибка отправки в чат {chat_id}: {e}")

            # Помечаем задание как выполненное
            await session.post(f"{SERVER_URL}/api/bot/queue/{job['id']}/done", headers=BOT_HEADERS)


async def queue_polling_loop(bot, interval_seconds=5):
    """Бесконечный цикл проверки очереди."""
    while True:
        try:
            await process_send_queue(bot)
        except Exception as e:
            print(f"Ошибка обработки очереди: {e}")
        await asyncio.sleep(interval_seconds)


# ── Логирование сообщений отправленных САМИМ БОТОМ ───────────────────────────

async def log_bot_send(session, chat_id: int, chat_name: str, message_text: str,
                        telegram_message_id: int = None, emergency_type: str = None):
    """
    Вызывай когда бот сам отправляет сообщение (не из очереди портала).
    Это обеспечит попадание данных в общий Excel-отчёт.
    """
    await log_message(session, None, emergency_type, chat_id, chat_name,
                      message_text, telegram_message_id, sent_by="bot")


# ── Команда /chatid — узнать ID чата ─────────────────────────────────────────

# Добавь этот handler в своего бота:
#
# @dp.message(Command("chatid"))
# async def cmd_chatid(message: types.Message):
#     await message.answer(f"Chat ID этого чата: <code>{message.chat.id}</code>", parse_mode="HTML")


# ── Пример запуска (добавь в свой main.py) ───────────────────────────────────

"""
from bot_integration import queue_polling_loop

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # ... регистрируй своих handlers ...

    # Запускаем опрос очереди параллельно
    asyncio.create_task(queue_polling_loop(bot, interval_seconds=5))

    await dp.start_polling(bot)
"""
