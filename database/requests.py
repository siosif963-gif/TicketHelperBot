# bot/database/requests.py
import logging
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError

from database.engine import async_session
from database.models import (
    ROLE_ADMIN,
    ROLE_CLIENT,
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_NEW,
    STATUS_REJECTED,
    Ticket,
    User,
)

logger = logging.getLogger(__name__)


async def get_or_create_user(telegram_id: int, username: str | None) -> User:
    """Возвращает пользователя; создаёт (role='client') или обновляет username."""
    try:
        async with async_session() as session:
            user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
            if user is None:
                user = User(telegram_id=telegram_id, username=username, role=ROLE_CLIENT)
                session.add(user)
            elif user.username != username:
                user.username = username
            await session.commit()
            return user
    except SQLAlchemyError:
        logger.exception("Ошибка get_or_create_user(%s)", telegram_id)
        raise


async def get_user(telegram_id: int) -> User | None:
    """Возвращает пользователя по Telegram ID или None."""
    try:
        async with async_session() as session:
            return await session.scalar(select(User).where(User.telegram_id == telegram_id))
    except SQLAlchemyError:
        logger.exception("Ошибка get_user(%s)", telegram_id)
        raise


async def set_user_role(telegram_id: int, role: str) -> None:
    """Устанавливает роль пользователя."""
    try:
        async with async_session() as session:
            await session.execute(update(User).where(User.telegram_id == telegram_id).values(role=role))
            await session.commit()
    except SQLAlchemyError:
        logger.exception("Ошибка set_user_role(%s, %s)", telegram_id, role)
        raise


async def get_admin_ids() -> list[int]:
    """Возвращает Telegram ID всех администраторов."""
    try:
        async with async_session() as session:
            result = await session.scalars(select(User.telegram_id).where(User.role == ROLE_ADMIN))
            return list(result.all())
    except SQLAlchemyError:
        logger.exception("Ошибка get_admin_ids")
        raise


async def create_ticket(
    user_tg_id: int, category: str, description: str, photo_file_id: str | None
) -> Ticket:
    """Создаёт новую заявку со статусом 'new'."""
    try:
        async with async_session() as session:
            ticket = Ticket(
                user_tg_id=user_tg_id,
                category=category,
                description=description,
                photo_file_id=photo_file_id,
                status=STATUS_NEW,
            )
            session.add(ticket)
            await session.commit()
            return ticket
    except SQLAlchemyError:
        logger.exception("Ошибка create_ticket(user=%s)", user_tg_id)
        raise


async def get_ticket(ticket_id: int) -> Ticket | None:
    """Возвращает заявку по номеру или None."""
    try:
        async with async_session() as session:
            return await session.get(Ticket, ticket_id)
    except SQLAlchemyError:
        logger.exception("Ошибка get_ticket(%s)", ticket_id)
        raise


async def get_user_tickets(user_tg_id: int, limit: int = 5) -> list[Ticket]:
    """Последние заявки пользователя (новые сверху)."""
    try:
        async with async_session() as session:
            result = await session.scalars(
                select(Ticket)
                .where(Ticket.user_tg_id == user_tg_id)
                .order_by(Ticket.created_at.desc(), Ticket.id.desc())
                .limit(limit)
            )
            return list(result.all())
    except SQLAlchemyError:
        logger.exception("Ошибка get_user_tickets(%s)", user_tg_id)
        raise


async def get_first_new_ticket() -> Ticket | None:
    """Самая старая заявка со статусом 'new'."""
    try:
        async with async_session() as session:
            return await session.scalar(
                select(Ticket).where(Ticket.status == STATUS_NEW).order_by(Ticket.id.asc()).limit(1)
            )
    except SQLAlchemyError:
        logger.exception("Ошибка get_first_new_ticket")
        raise


async def get_next_new_ticket(current_id: int) -> Ticket | None:
    """Следующая новая заявка после current_id (по кругу) или None."""
    try:
        async with async_session() as session:
            ticket = await session.scalar(
                select(Ticket)
                .where(Ticket.status == STATUS_NEW, Ticket.id > current_id)
                .order_by(Ticket.id.asc())
                .limit(1)
            )
            if ticket is None:
                ticket = await session.scalar(
                    select(Ticket)
                    .where(Ticket.status == STATUS_NEW, Ticket.id != current_id)
                    .order_by(Ticket.id.asc())
                    .limit(1)
                )
            return ticket
    except SQLAlchemyError:
        logger.exception("Ошибка get_next_new_ticket(%s)", current_id)
        raise


async def take_ticket(ticket_id: int, admin_tg_id: int) -> bool:
    """Атомарно берёт заявку в работу. True, если заявка была 'new'."""
    try:
        async with async_session() as session:
            result = await session.execute(
                update(Ticket)
                .where(Ticket.id == ticket_id, Ticket.status == STATUS_NEW)
                .values(status=STATUS_IN_PROGRESS, admin_tg_id=admin_tg_id, updated_at=datetime.now())
            )
            await session.commit()
            return result.rowcount == 1
    except SQLAlchemyError:
        logger.exception("Ошибка take_ticket(%s)", ticket_id)
        raise


async def close_ticket(ticket_id: int, admin_tg_id: int, comment: str, report_photo_id: str) -> bool:
    """Закрывает заявку с отчётом. True, если заявка была в работе у этого админа."""
    try:
        async with async_session() as session:
            result = await session.execute(
                update(Ticket)
                .where(
                    Ticket.id == ticket_id,
                    Ticket.status == STATUS_IN_PROGRESS,
                    Ticket.admin_tg_id == admin_tg_id,
                )
                .values(
                    status=STATUS_DONE,
                    admin_comment=comment,
                    report_photo_id=report_photo_id,
                    updated_at=datetime.now(),
                )
            )
            await session.commit()
            return result.rowcount == 1
    except SQLAlchemyError:
        logger.exception("Ошибка close_ticket(%s)", ticket_id)
        raise


async def reject_ticket(ticket_id: int, admin_tg_id: int, reason: str) -> bool:
    """Отклоняет новую заявку. True, если заявка была 'new'."""
    try:
        async with async_session() as session:
            result = await session.execute(
                update(Ticket)
                .where(Ticket.id == ticket_id, Ticket.status == STATUS_NEW)
                .values(
                    status=STATUS_REJECTED,
                    admin_tg_id=admin_tg_id,
                    admin_comment=reason,
                    updated_at=datetime.now(),
                )
            )
            await session.commit()
            return result.rowcount == 1
    except SQLAlchemyError:
        logger.exception("Ошибка reject_ticket(%s)", ticket_id)
        raise


async def get_admin_in_progress(admin_tg_id: int, limit: int = 10) -> list[Ticket]:
    """Заявки в работе у конкретного администратора."""
    try:
        async with async_session() as session:
            result = await session.scalars(
                select(Ticket)
                .where(Ticket.status == STATUS_IN_PROGRESS, Ticket.admin_tg_id == admin_tg_id)
                .order_by(Ticket.id.asc())
                .limit(limit)
            )
            return list(result.all())
    except SQLAlchemyError:
        logger.exception("Ошибка get_admin_in_progress(%s)", admin_tg_id)
        raise


async def get_closed_tickets(limit: int = 10) -> list[Ticket]:
    """Последние закрытые (выполненные и отклонённые) заявки."""
    try:
        async with async_session() as session:
            result = await session.scalars(
                select(Ticket)
                .where(Ticket.status.in_([STATUS_DONE, STATUS_REJECTED]))
                .order_by(Ticket.updated_at.desc(), Ticket.id.desc())
                .limit(limit)
            )
            return list(result.all())
    except SQLAlchemyError:
        logger.exception("Ошибка get_closed_tickets")
        raise


async def get_stats() -> dict[str, int]:
    """Количество заявок по статусам."""
    try:
        async with async_session() as session:
            rows = await session.execute(select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status))
            stats = {STATUS_NEW: 0, STATUS_IN_PROGRESS: 0, STATUS_DONE: 0, STATUS_REJECTED: 0}
            for status, count in rows.all():
                stats[status] = count
            return stats
    except SQLAlchemyError:
        logger.exception("Ошибка get_stats")
        raise
