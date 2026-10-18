# bot/handlers/common.py
import html
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message, ReplyKeyboardMarkup

from config import ADMIN_IDS
from database.models import ROLE_ADMIN
from database.requests import get_or_create_user, get_user, set_user_role
from keyboards.inline import CB_CANCEL_FORM
from keyboards.reply import BTN_CANCEL, BTN_HELP, admin_menu_kb, main_menu_kb
from utils.formatters import safe_delete

logger = logging.getLogger(__name__)

router = Router()

HELP_TEXT = (
    "ℹ️ <b>Помощь</b>\n\n"
    "Чтобы подать заявку, нажмите «📝 Подать заявку», выберите категорию, "
    "опишите проблему и при желании прикрепите фото.\n\n"
    "<b>Статусы заявок:</b>\n"
    "🟡 Новая — заявка принята и ожидает обработки\n"
    "🔵 В работе — администратор занимается заявкой\n"
    "🟢 Выполнена — проблема решена\n"
    "🔴 Отклонена — заявка отклонена, причина указана в ответе\n\n"
    "Команда /cancel отменяет текущее действие."
)


async def _menu_for(user_id: int) -> ReplyKeyboardMarkup:
    """Возвращает меню в зависимости от роли пользователя."""
    user = await get_user(user_id)
    if user is not None and user.role == ROLE_ADMIN:
        return admin_menu_kb()
    return main_menu_kb()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await get_or_create_user(message.from_user.id, message.from_user.username)
    if message.from_user.id in ADMIN_IDS:
        await set_user_role(message.from_user.id, ROLE_ADMIN)
    name = html.escape(message.from_user.full_name)
    await message.answer(
        f"👋 Здравствуйте, {name}! Это бот приёма заявок и жалоб. "
        "Выберите действие в меню ниже.",
        reply_markup=await _menu_for(message.from_user.id),
    )


@router.message(Command("cancel"))
@router.message(F.text == BTN_CANCEL)
async def cancel_any_state(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=await _menu_for(message.from_user.id))


@router.callback_query(F.data == CB_CANCEL_FORM)
async def cancel_form_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_delete(callback.message)
    await callback.bot.send_message(
        callback.from_user.id,
        "Действие отменено.",
        reply_markup=await _menu_for(callback.from_user.id),
    )
    await callback.answer()


@router.message(F.text == BTN_HELP)
async def show_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(HELP_TEXT)


@router.errors()
async def global_error_handler(event: ErrorEvent) -> bool:
    logger.exception("Ошибка: %s", event.exception, exc_info=event.exception)
    text = "⚠️ Произошла ошибка, попробуйте позже."
    try:
        update = event.update
        if update.message:
            await update.message.answer(text)
        elif update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
    except Exception:
        logger.exception("Не удалось сообщить пользователю об ошибке")
    return True
