# bot/handlers/admin.py
import html
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import check_password
from database.models import ROLE_ADMIN, ROLE_CLIENT, STATUS_IN_PROGRESS, STATUS_NEW
from database.requests import (
    close_ticket,
    get_admin_in_progress,
    get_closed_tickets,
    get_first_new_ticket,
    get_or_create_user,
    get_next_new_ticket,
    get_stats,
    get_ticket,
    get_user,
    reject_ticket,
    set_user_role,
    take_ticket,
)
from filters.is_admin import IsAdmin
from keyboards.inline import (
    CB_ADMIN_LOGOUT,
    TicketCB,
    in_progress_actions_kb,
    in_progress_list_kb,
    new_ticket_actions_kb,
    settings_kb,
)
from keyboards.reply import (
    BTN_ADMIN_CLOSED,
    BTN_ADMIN_IN_PROGRESS,
    BTN_ADMIN_NEW,
    BTN_ADMIN_SETTINGS,
    MENU_TEXTS,
    admin_menu_kb,
    cancel_kb,
    main_menu_kb,
)
from states.states import AdminAuth, AdminProcess
from utils.formatters import (
    format_ticket_card,
    format_ticket_with_reply,
    safe_delete,
    safe_send,
    send_ticket_card,
)

logger = logging.getLogger(__name__)

MAX_TEXT = 800

auth_router = Router()
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ======================= Вход в админку =======================

@auth_router.message(Command("admin"))
@auth_router.message(F.text == "Режим админа")
async def admin_login(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(message.from_user.id)
    if user is not None and user.role == ROLE_ADMIN:
        await message.answer("Вы уже администратор.", reply_markup=admin_menu_kb())
        return
    await state.set_state(AdminAuth.wait_admin_password)
    await message.answer("🔐 Введите PIN-код:", reply_markup=cancel_kb())


@auth_router.message(AdminAuth.wait_admin_password, F.text)
async def admin_check_password(message: Message, state: FSMContext) -> None:
    await safe_delete(message)
    user_id = message.from_user.id
    if check_password(message.text.strip()):
        # Пользователь мог быть не создан (нет /start) — гарантируем запись.
        await get_or_create_user(user_id, message.from_user.username)
        await set_user_role(user_id, ROLE_ADMIN)
        await state.clear()
        logger.info("Пользователь %s получил роль admin", user_id)
        await message.answer(
            "✅ Доступ разрешён. Добро пожаловать в админ-панель.", reply_markup=admin_menu_kb()
        )
    else:
        await state.clear()
        logger.warning("Неверный PIN от пользователя %s", user_id)
        await message.answer("⛔ Доступ запрещён.", reply_markup=main_menu_kb())


@auth_router.message(AdminAuth.wait_admin_password)
async def admin_password_fallback(message: Message) -> None:
    await message.answer("Введите PIN-код текстом.")


# ======================= Меню админа =======================

async def show_new_ticket(bot: Bot, chat_id: int, ticket_id: int) -> bool:
    """Показывает карточку новой заявки. False, если заявка не найдена."""
    ticket = await get_ticket(ticket_id)
    if ticket is None:
        return False
    author = await get_user(ticket.user_tg_id)
    await send_ticket_card(bot, chat_id, ticket, format_ticket_card(ticket, author), new_ticket_actions_kb(ticket.id))
    return True


@router.message(F.text == BTN_ADMIN_NEW)
async def menu_new_tickets(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    ticket = await get_first_new_ticket()
    if ticket is None:
        await message.answer("📭 Новых заявок нет.")
        return
    await show_new_ticket(bot, message.chat.id, ticket.id)


@router.message(F.text == BTN_ADMIN_IN_PROGRESS)
async def menu_in_progress(message: Message, state: FSMContext) -> None:
    await state.clear()
    tickets = await get_admin_in_progress(message.from_user.id)
    if not tickets:
        await message.answer("У вас нет заявок в работе.")
        return
    await message.answer("🔄 Ваши заявки в работе:", reply_markup=in_progress_list_kb(tickets))


@router.message(F.text == BTN_ADMIN_CLOSED)
async def menu_closed(message: Message, state: FSMContext) -> None:
    await state.clear()
    tickets = await get_closed_tickets(10)
    if not tickets:
        await message.answer("Закрытых заявок пока нет.")
        return
    items = "\n\n".join(format_ticket_with_reply(t) for t in tickets)
    await message.answer(f"✅ <b>Закрытые заявки:</b>\n\n{items}")


@router.message(F.text == BTN_ADMIN_SETTINGS)
async def menu_settings(message: Message, state: FSMContext) -> None:
    await state.clear()
    stats = await get_stats()
    await message.answer(
        "⚙️ <b>Настройки</b>\n"
        f"👤 Ваш ID: <code>{message.from_user.id}</code>\n\n"
        "📊 Статистика заявок:\n"
        f"🟡 Новые: {stats['new']}\n"
        f"🔵 В работе: {stats['in_progress']}\n"
        f"🟢 Выполнены: {stats['done']}\n"
        f"🔴 Отклонены: {stats['rejected']}",
        reply_markup=settings_kb(),
    )


@router.callback_query(F.data == CB_ADMIN_LOGOUT)
async def admin_logout(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await set_user_role(callback.from_user.id, ROLE_CLIENT)
    logger.info("Пользователь %s вышел из режима admin", callback.from_user.id)
    await safe_delete(callback.message)
    await callback.bot.send_message(
        callback.from_user.id, "Вы вышли из режима администратора.", reply_markup=main_menu_kb()
    )
    await callback.answer()


# ======================= Действия над заявками =======================

@router.callback_query(TicketCB.filter(F.action == "take"))
async def ticket_take(callback: CallbackQuery, callback_data: TicketCB, bot: Bot) -> None:
    ticket_id = callback_data.ticket_id
    if not await take_ticket(ticket_id, callback.from_user.id):
        await callback.answer("Заявку уже обработал другой администратор.", show_alert=True)
        return
    ticket = await get_ticket(ticket_id)
    await safe_delete(callback.message)
    if ticket is not None:
        await safe_send(bot, ticket.user_tg_id, f"🔵 Ваша заявка №{ticket.id} взята в работу.")
        author = await get_user(ticket.user_tg_id)
        await send_ticket_card(
            bot,
            callback.from_user.id,
            ticket,
            format_ticket_card(ticket, author),
            in_progress_actions_kb(ticket.id),
        )
    await callback.answer("Заявка взята в работу")


@router.callback_query(TicketCB.filter(F.action == "next"))
async def ticket_next(callback: CallbackQuery, callback_data: TicketCB, bot: Bot) -> None:
    ticket = await get_next_new_ticket(callback_data.ticket_id)
    if ticket is None:
        await callback.answer("Других новых заявок нет.", show_alert=True)
        return
    await safe_delete(callback.message)
    await show_new_ticket(bot, callback.from_user.id, ticket.id)
    await callback.answer()


@router.callback_query(TicketCB.filter(F.action == "reject"))
async def ticket_reject(callback: CallbackQuery, callback_data: TicketCB, state: FSMContext) -> None:
    ticket = await get_ticket(callback_data.ticket_id)
    if ticket is None or ticket.status != STATUS_NEW:
        await callback.answer("Заявка уже обработана.", show_alert=True)
        return
    await state.set_state(AdminProcess.wait_reject_reason)
    await state.update_data(ticket_id=ticket.id)
    await callback.bot.send_message(
        callback.from_user.id,
        f"✍️ Укажите причину отклонения заявки №{ticket.id}:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminProcess.wait_reject_reason, F.text, ~F.text.in_(MENU_TEXTS))
async def reject_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    reason = message.text.strip()
    if not reason or len(reason) > MAX_TEXT:
        await message.answer("Причина должна быть от 1 до 800 символов. Сократите текст.")
        return
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    await state.clear()
    if ticket_id is None:
        await message.answer("Заявка не найдена, начните заново.", reply_markup=admin_menu_kb())
        return
    if not await reject_ticket(ticket_id, message.from_user.id, reason):
        await message.answer("Заявка уже обработана другим администратором.", reply_markup=admin_menu_kb())
        return
    ticket = await get_ticket(ticket_id)
    if ticket is not None:
        await safe_send(
            bot,
            ticket.user_tg_id,
            f"🔴 Ваша заявка №{ticket_id} отклонена.\nПричина: {html.escape(reason)}",
        )
    await message.answer(f"Заявка №{ticket_id} отклонена.", reply_markup=admin_menu_kb())


@router.message(AdminProcess.wait_reject_reason)
async def reject_reason_fallback(message: Message) -> None:
    await message.answer("Отправьте причину текстом или нажмите «❌ Отмена».")


@router.callback_query(TicketCB.filter(F.action == "close"))
async def ticket_close(callback: CallbackQuery, callback_data: TicketCB, state: FSMContext) -> None:
    ticket = await get_ticket(callback_data.ticket_id)
    if (
        ticket is None
        or ticket.status != STATUS_IN_PROGRESS
        or ticket.admin_tg_id != callback.from_user.id
    ):
        await callback.answer("Закрыть может только администратор, взявший заявку", show_alert=True)
        return
    await state.set_state(AdminProcess.wait_admin_comment)
    await state.update_data(ticket_id=ticket.id)
    await callback.bot.send_message(
        callback.from_user.id,
        f"📝 Опишите, что было сделано по заявке №{ticket.id} (до 800 символов):",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminProcess.wait_admin_comment, F.text, ~F.text.in_(MENU_TEXTS))
async def close_comment(message: Message, state: FSMContext) -> None:
    comment = message.text.strip()
    if not comment or len(comment) > MAX_TEXT:
        await message.answer("Комментарий должен быть от 1 до 800 символов. Сократите текст.")
        return
    await state.update_data(comment=comment)
    await state.set_state(AdminProcess.wait_admin_photo)
    await message.answer("📸 Пришлите фото результата работ.")


@router.message(AdminProcess.wait_admin_comment)
async def close_comment_fallback(message: Message) -> None:
    await message.answer("Отправьте комментарий текстом или нажмите «❌ Отмена».")


@router.message(AdminProcess.wait_admin_photo, F.photo)
async def close_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    comment = data.get("comment")
    await state.clear()
    if ticket_id is None or comment is None:
        await message.answer("Данные утеряны, начните заново.", reply_markup=admin_menu_kb())
        return
    report_photo_id = message.photo[-1].file_id
    if not await close_ticket(ticket_id, message.from_user.id, comment, report_photo_id):
        await message.answer("Не удалось закрыть заявку (статус изменился).", reply_markup=admin_menu_kb())
        return
    ticket = await get_ticket(ticket_id)
    if ticket is not None:
        text = (
            f"🟢 Заявка №{ticket_id} выполнена!\n\n"
            f"💬 Комментарий администратора:\n{html.escape(comment)}"
        )
        await safe_send(bot, ticket.user_tg_id, text, photo=report_photo_id)
    await message.answer(f"✅ Заявка №{ticket_id} закрыта, клиент уведомлён.", reply_markup=admin_menu_kb())


@router.message(AdminProcess.wait_admin_photo)
async def close_photo_fallback(message: Message) -> None:
    await message.answer("Пришлите именно фото (не файлом).")


@router.callback_query(TicketCB.filter(F.action == "back"))
async def ticket_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_delete(callback.message)
    await callback.bot.send_message(callback.from_user.id, "Админ-меню:", reply_markup=admin_menu_kb())
    await callback.answer()


@router.callback_query(TicketCB.filter(F.action == "open"))
async def ticket_open(callback: CallbackQuery, callback_data: TicketCB, bot: Bot) -> None:
    ticket = await get_ticket(callback_data.ticket_id)
    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    author = await get_user(ticket.user_tg_id)
    markup = in_progress_actions_kb(ticket.id) if ticket.status == STATUS_IN_PROGRESS else None
    await safe_delete(callback.message)
    await send_ticket_card(bot, callback.from_user.id, ticket, format_ticket_card(ticket, author), markup)
    await callback.answer()
