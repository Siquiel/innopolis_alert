from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


def build_buttons_markup(buttons: list[dict[str, str]] | None):
    if not buttons:
        return None
    rows = []
    for btn in buttons:
        text = btn.get("text", "").strip()
        url = btn.get("url", "").strip()
        if not text or not url:
            continue
        if not url.startswith(("http://", "https://", "tg://")):
            url = "https://" + url
        rows.append([InlineKeyboardButton(text=text, url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def send_alert_to_moderator(bot: Bot, moderator_chat_id: int | None, text: str) -> None:
    if moderator_chat_id is None:
        logger.warning("Moderator chat is not configured: %s", text)
        return
    try:
        await bot.send_message(moderator_chat_id, text)
    except Exception:
        logger.exception("Failed to send moderator notification")


async def send_rich_message(
    bot: Bot,
    chat_id: int,
    text: str,
    media_type: str = "",
    media_file_id: str = "",
    buttons: list[dict[str, str]] | None = None,
) -> None:
    markup = build_buttons_markup(buttons)
    if media_type == "photo" and media_file_id:
        await bot.send_photo(chat_id=chat_id, photo=media_file_id, caption=text, reply_markup=markup)
        return
    if media_type == "video" and media_file_id:
        await bot.send_video(chat_id=chat_id, video=media_file_id, caption=text, reply_markup=markup)
        return
    if media_type == "document" and media_file_id:
        await bot.send_document(chat_id=chat_id, document=media_file_id, caption=text, reply_markup=markup)
        return
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
