from __future__ import annotations

from aiogram import F, Router
from aiogram.types import ChatMemberUpdated, Message

router = Router(name="system")


@router.my_chat_member()
async def track_bot_added(event: ChatMemberUpdated, storage, pg_sync=None) -> None:
    new_status = event.new_chat_member.status
    if new_status not in {"member", "administrator"}:
        if new_status in {"left", "kicked"}:
            storage.set_chat_active(event.chat.id, False)
        return
    title = event.chat.title or event.chat.full_name or str(event.chat.id)
    storage.upsert_managed_chat(event.chat.id, title, event.chat.type, username=event.chat.username or "", auto_registered=True)
    if pg_sync:
        await pg_sync.register_chat_to_pg(event.chat.id, title)


@router.message(~F.chat.type.in_({"private"}))
async def passive_group_listener(message: Message, storage, pg_sync=None) -> None:
    title = message.chat.title or message.chat.full_name or str(message.chat.id)
    storage.upsert_managed_chat(message.chat.id, title, message.chat.type, username=message.chat.username or "", auto_registered=True)
    if pg_sync:
        await pg_sync.register_chat_to_pg(message.chat.id, title)
