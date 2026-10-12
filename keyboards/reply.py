# bot/keyboards/reply.py
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_NEW_TICKET = "📝 Подать заявку"
BTN_MY_TICKETS = "📋 Мои заявки"
BTN_HELP = "ℹ️ Помощь"
BTN_CANCEL = "❌ Отмена"

BTN_ADMIN_NEW = "📥 Новые заявки"
BTN_ADMIN_IN_PROGRESS = "🔄 В работе"
BTN_ADMIN_CLOSED = "✅ Закрытые"
BTN_ADMIN_SETTINGS = "⚙️ Настройки"


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Главное меню клиента."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_NEW_TICKET), KeyboardButton(text=BTN_MY_TICKETS)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def admin_menu_kb() -> ReplyKeyboardMarkup:
    """Меню администратора."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ADMIN_NEW), KeyboardButton(text=BTN_ADMIN_IN_PROGRESS)],
            [KeyboardButton(text=BTN_ADMIN_CLOSED), KeyboardButton(text=BTN_ADMIN_SETTINGS)],
        ],
        resize_keyboard=True,
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    """Клавиатура с одной кнопкой отмены."""
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)
