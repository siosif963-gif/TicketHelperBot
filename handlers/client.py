# bot/handlers/client.py
import html
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.requests import create_ticket, get_admin_ids, get_user_tickets
from keyboards.inline import (
    CATEGORIES,
    CB_CONFIRM_SEND,
    CB_SKIP_PHOTO,
    CategoryCB,
    categories_kb,
    confirm_kb,
    skip_photo_kb,
)
from keyboards.reply import BTN_MY_TICKETS, BTN_NEW_TICKET, cancel_kb, main_menu_kb
from states.states import TicketForm
from utils.formatters import (
    format_ticket_with_reply,
    safe_delete,
    safe_send,
    send_text_or_photo,
)

logger = logging.getLogger(__name__)

router = Router()

MIN_DESCRIPTION = 10
MAX_DESCRIPTION = 800


# ---------- Кнопки главного меню (без фильтра состояния, всегда сбрасывают FSM) ----------

@router.message(F.text == BTN_NEW_TICKET)
async def start_ticket(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(TicketForm.choose_category)
    await message.answer(
        "📝 Оформление заявки. Для отмены нажмите «❌ Отмена».", reply_markup=cancel_kb()
    )
    await message.answer("Шаг 1/4. Выберите категорию:", reply_markup=categories_kb())


@router.message(F.text == BTN_MY_TICKETS)
async def my_tickets(message: Message, state: FSMContext) -> None:
    await state.clear()
    tickets = await get_user_tickets(message.from_user.id, 5)
    if not tickets:
        await message.answer("У вас пока нет заявок.")
        return
    items = "\n\n".join(format_ticket_with_reply(t) for t in tickets)
    await message.answer(f"📋 <b>Ваши последние заявки:</b>\n\n{items}")


# ---------- Шаг 1: категория ----------

@router.callback_query(TicketForm.choose_category, CategoryCB.filter())
async def choose_category(callback: CallbackQuery, callback_data: CategoryCB, state: FSMContext) -> None:
    category = CATEGORIES.get(callback_data.code)
    if category is None:
        await callback.answer("Неизвестная категория.", show_alert=True)
        return
    await state.update_data(category=category)
    await state.set_state(TicketForm.enter_description)
    await safe_delete(callback.message)
    await callback.bot.send_message(
        callback.from_user.id,
        f"Шаг 2/4. Опишите проблему текстом (от {MIN_DESCRIPTION} до {MAX_DESCRIPTION} символов).",
    )
    await callback.answer()


@router.message(TicketForm.choose_category)
async def choose_category_fallback(message: Message) -> None:
    await message.answer("Пожалуйста, выберите категорию кнопкой выше.")


# ---------- Шаг 2: описание ----------

@router.message(TicketForm.enter_description, F.text)
async def enter_description(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if len(text) < MIN_DESCRIPTION:
        await message.answer("Слишком коротко, опишите подробнее (минимум 10 символов).")
        return
    if len(text) > MAX_DESCRIPTION:
        await message.answer("Слишком длинно, сократите до 800 символов.")
        return
    await state.update_data(description=text)
    await state.set_state(TicketForm.upload_photo)
    await message.answer(
        "Шаг 3/4. Прикрепите фото проблемы или нажмите «Пропустить».",
        reply_markup=skip_photo_kb(),
    )


@router.message(TicketForm.enter_description)
async def enter_description_fallback(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте описание текстом.")


# ---------- Шаг 3: фото ----------

async def show_confirmation(target: Message | CallbackQuery, state: FSMContext) -> None:
    """Показывает сводку заявки и просит подтверждение."""
    data = await state.get_data()
    await state.set_state(TicketForm.confirm)
    text = (
        "Шаг 4/4. Проверьте заявку:\n"
        f"📂 Категория: {html.escape(data['category'])}\n"
        f"📝 Описание: {html.escape(data['description'])}"
    )
    await send_text_or_photo(
        target.bot,
        target.from_user.id,
        text,
        photo=data.get("photo_file_id"),
        reply_markup=confirm_kb(),
    )


@router.message(TicketForm.upload_photo, F.photo)
async def upload_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await show_confirmation(message, state)


@router.callback_query(TicketForm.upload_photo, F.data == CB_SKIP_PHOTO)
async def skip_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(photo_file_id=None)
    await safe_delete(callback.message)
    await show_confirmation(callback, state)
    await callback.answer()


@router.message(TicketForm.upload_photo, F.document)
async def upload_photo_document(message: Message) -> None:
    await message.answer("Отправьте изображение как фото (со сжатием), а не файлом.")


@router.message(TicketForm.upload_photo)
async def upload_photo_fallback(message: Message) -> None:
    await message.answer("Пришлите фото или нажмите «Пропустить».")


# ---------- Шаг 4: подтверждение ----------

@router.callback_query(TicketForm.confirm, F.data == CB_CONFIRM_SEND)
async def confirm_send(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    category = data.get("category")
    description = data.get("description")
    if not category or not description:
        await state.clear()
        await safe_delete(callback.message)
        await callback.answer("Данные заявки утеряны, начните заново.", show_alert=True)
        return

    ticket = await create_ticket(
        user_tg_id=callback.from_user.id,
        category=category,
        description=description,
        photo_file_id=data.get("photo_file_id"),
    )
    await state.clear()
    await safe_delete(callback.message)
    await bot.send_message(
        callback.from_user.id,
        f"✅ Заявка №{ticket.id} принята! Мы уведомим вас об изменении статуса.",
        reply_markup=main_menu_kb(),
    )
    for admin_id in await get_admin_ids():
        await safe_send(bot, admin_id, f"🚨 Новая заявка №{ticket.id}! Зайдите в админ-панель.")
    await callback.answer()


@router.message(TicketForm.confirm)
async def confirm_fallback(message: Message) -> None:
    await message.answer("Нажмите «✅ Отправить» или «❌ Отмена» под заявкой.")


# ---------- Устаревшие кнопки (состояние потеряно) ----------

@router.callback_query(F.data.in_({CB_SKIP_PHOTO, CB_CONFIRM_SEND}))
@router.callback_query(CategoryCB.filter())
async def stale_form_buttons(callback: CallbackQuery) -> None:
    await safe_delete(callback.message)
    await callback.answer("Сессия устарела. Начните заявку заново.", show_alert=True)
