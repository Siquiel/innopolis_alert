from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.keyboards import home_kb

router = Router(name="user")


@router.message(CommandStart())
async def cmd_start(message: Message, storage, pg_auth=None) -> None:
    if message.chat.type != "private":
        await message.answer("Бот активен. Админка доступна только в личном чате.")
        return

    user = message.from_user
    if not user:
        await message.answer("Не удалось определить пользователя Telegram.")
        return

    # first private user can bootstrap the bot locally
    if not storage.has_any_admins():
        storage.upsert_admin(user.id, user.full_name, user.username or "", role="superadmin")

    # optional PostgreSQL auth sync
    if not storage.is_admin(user.id) and pg_auth:
        external_admin = pg_auth.get_admin(user.id)
        if external_admin:
            storage.upsert_admin(
                external_admin.telegram_id,
                external_admin.full_name or user.full_name,
                external_admin.username or (user.username or ""),
                external_admin.role or "admin",
            )

    if storage.is_admin(user.id):
        storage.upsert_admin(user.id, user.full_name, user.username or "")
        greeting = storage.get_setting("staff_greeting")
        await message.answer(greeting, reply_markup=home_kb())
        return

    auth_hint = (
        "Доступ открывается администраторам из PostgreSQL (таблица <code>bot_admins</code>) "
        "или локальным администраторам бота."
    )
    await message.answer(
        "Это служебный бот локального оповещения.\n\n"
        "У вас нет прав администратора.\n"
        f"{auth_hint}"
    )


@router.message(CommandStart(deep_link=False))
async def fallback_start(message: Message) -> None:
    return
