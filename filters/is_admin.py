# bot/filters/is_admin.py
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from database.models import ROLE_ADMIN
from database.requests import get_user


class IsAdmin(BaseFilter):
    """Пропускает только пользователей с ролью admin (проверка по БД)."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if event.from_user is None:
            return False
        user = await get_user(event.from_user.id)
        return user is not None and user.role == ROLE_ADMIN
