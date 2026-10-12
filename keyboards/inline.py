# bot/keyboards/inline.py
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import Ticket

CATEGORIES: dict[str, str] = {
    "utility": "🏠 ЖКХ",
    "infra": "🛣 Инфраструктура",
    "other": "📦 Другое",
}

CB_SKIP_PHOTO = "skip_photo"
CB_CONFIRM_SEND = "confirm_send"
CB_CANCEL_FORM = "cancel_form"
CB_ADMIN_LOGOUT = "admin_logout"


class CategoryCB(CallbackData, prefix="cat"):
    code: str


class TicketCB(CallbackData, prefix="tk"):
    action: str
    ticket_id: int


def categories_kb() -> InlineKeyboardMarkup:
    """Выбор категории заявки."""
    builder = InlineKeyboardBuilder()
    for code, title in CATEGORIES.items():
        builder.button(text=title, callback_data=CategoryCB(code=code))
    builder.button(text="❌ Отмена", callback_data=CB_CANCEL_FORM)
    builder.adjust(1)
    return builder.as_markup()


def skip_photo_kb() -> InlineKeyboardMarkup:
    """Пропуск фото."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ Пропустить", callback_data=CB_SKIP_PHOTO)
    builder.button(text="❌ Отмена", callback_data=CB_CANCEL_FORM)
    builder.adjust(1)
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    """Подтверждение отправки заявки."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить", callback_data=CB_CONFIRM_SEND)
    builder.button(text="❌ Отмена", callback_data=CB_CANCEL_FORM)
    builder.adjust(2)
    return builder.as_markup()


def new_ticket_actions_kb(ticket_id: int) -> InlineKeyboardMarkup:
    """Действия админа над новой заявкой."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Взять в работу", callback_data=TicketCB(action="take", ticket_id=ticket_id))
    builder.button(text="❌ Отклонить", callback_data=TicketCB(action="reject", ticket_id=ticket_id))
    builder.button(text="➡️ Следующая", callback_data=TicketCB(action="next", ticket_id=ticket_id))
    builder.adjust(2, 1)
    return builder.as_markup()


def in_progress_actions_kb(ticket_id: int) -> InlineKeyboardMarkup:
    """Действия админа над заявкой в работе."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏁 Закрыть с отчётом", callback_data=TicketCB(action="close", ticket_id=ticket_id))
    builder.button(text="🔙 Назад в меню", callback_data=TicketCB(action="back", ticket_id=ticket_id))
    builder.adjust(1)
    return builder.as_markup()


def in_progress_list_kb(tickets: list[Ticket]) -> InlineKeyboardMarkup:
    """Список заявок в работе: по кнопке на заявку."""
    builder = InlineKeyboardBuilder()
    for ticket in tickets:
        builder.button(
            text=f"№{ticket.id} · {ticket.category}",
            callback_data=TicketCB(action="open", ticket_id=ticket.id),
        )
    builder.adjust(1)
    return builder.as_markup()


def settings_kb() -> InlineKeyboardMarkup:
    """Настройки админа."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚪 Выйти из режима админа", callback_data=CB_ADMIN_LOGOUT)
    builder.adjust(1)
    return builder.as_markup()
