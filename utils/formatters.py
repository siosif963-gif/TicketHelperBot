# bot/utils/formatters.py
import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, Message

from database.models import STATUS_DONE, STATUS_REJECTED, Ticket, User

logger = logging.getLogger(__name__)

STATUS_LABELS: dict[str, str] = {
    "new": "🟡 Новая",
    "in_progress": "🔵 В работе",
    "done": "🟢 Выполнена",
    "rejected": "🔴 Отклонена",
}

CAPTION_LIMIT = 1024


def format_ticket_card(ticket: Ticket, user: User | None) -> str:
    """Карточка заявки для администратора."""
    if user is not None and user.username:
        client = f"@{html.escape(user.username)}"
    else:
        client = "без username"
    return (
        f"🎫 <b>Заявка №{ticket.id}</b>\n"
        f"📂 Категория: {html.escape(ticket.category)}\n"
        f"📌 Статус: {STATUS_LABELS.get(ticket.status, ticket.status)}\n"
        f"👤 Клиент: {client}, ID: <code>{ticket.user_tg_id}</code>\n"
        f"📅 Создана: {ticket.created_at:%d.%m.%Y %H:%M}\n\n"
        f"📝 <b>Описание:</b>\n{html.escape(ticket.description)}"
    )


def format_ticket_short(ticket: Ticket) -> str:
    """Короткая строка заявки для списков."""
    text = " ".join(ticket.description.split())
    preview = text[:60] + ("…" if len(text) > 60 else "")
    return (
        f"{STATUS_LABELS.get(ticket.status, ticket.status)} <b>№{ticket.id}</b> · "
        f"{html.escape(ticket.category)} · {ticket.created_at:%d.%m.%Y}\n"
        f"{html.escape(preview)}"
    )


def format_ticket_with_reply(ticket: Ticket) -> str:
    """Короткая строка + ответ администратора для выполненных/отклонённых заявок."""
    text = format_ticket_short(ticket)
    if ticket.status in (STATUS_DONE, STATUS_REJECTED) and ticket.admin_comment:
        text += f"\n💬 Ответ: {html.escape(ticket.admin_comment)}"
    return text


async def send_text_or_photo(
    bot: Bot,
    chat_id: int,
    text: str,
    photo: str | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    """Отправляет фото с подписью (если влезает в лимит) или обычный текст."""
    if photo is None:
        return await bot.send_message(chat_id, text, reply_markup=reply_markup)
    if len(text) <= CAPTION_LIMIT:
        return await bot.send_photo(chat_id, photo, caption=text, reply_markup=reply_markup)
    await bot.send_photo(chat_id, photo)
    return await bot.send_message(chat_id, text, reply_markup=reply_markup)


async def send_ticket_card(
    bot: Bot,
    chat_id: int,
    ticket: Ticket,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    """Отправляет карточку заявки: с фото, если оно есть."""
    return await send_text_or_photo(bot, chat_id, text, ticket.photo_file_id, reply_markup)


async def safe_send(bot: Bot, chat_id: int, text: str, photo: str | None = None) -> bool:
    """Безопасная отправка уведомления; не падает, если бот заблокирован."""
    try:
        await send_text_or_photo(bot, chat_id, text, photo)
        return True
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        logger.warning("Не удалось отправить сообщение пользователю %s: %s", chat_id, e)
        return False


async def safe_delete(message: Message | None) -> None:
    """Безопасное удаление сообщения."""
    if message is None:
        return
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except TelegramBadRequest as e:
        logger.debug("Не удалось удалить сообщение: %s", e)
