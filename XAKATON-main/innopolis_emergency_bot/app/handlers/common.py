from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="common")


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    user = message.from_user
    text = (
        f"Ваш user_id: <code>{user.id if user else 'unknown'}</code>\n"
        f"Текущий chat_id: <code>{message.chat.id}</code>\n"
        f"Тип чата: <code>{message.chat.type}</code>"
    )
    await message.answer(text)


@router.message(Command("chatid"))
async def cmd_chatid(message: Message) -> None:
    title = message.chat.title or message.chat.full_name or "личный чат"
    text = (
        f"<b>Chat ID:</b> <code>{message.chat.id}</code>\n"
        f"<b>Название:</b> {title}\n"
        f"<b>Тип:</b> {message.chat.type}\n\n"
        f"Скопируйте этот ID и добавьте его в разделе «Telegram-чаты» на портале."
    )
    await message.answer(text)


@router.message(Command("register_here"), ~F.chat.type.in_({"private"}))
async def cmd_register_here(message: Message, storage) -> None:
    title = message.chat.title or message.chat.full_name or str(message.chat.id)
    username = message.chat.username or ""
    storage.upsert_managed_chat(message.chat.id, title, message.chat.type, username=username, auto_registered=False)
    await message.reply("Чат зарегистрирован в системе рассылки.")
