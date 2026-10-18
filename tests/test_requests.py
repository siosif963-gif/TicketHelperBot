# bot/tests/test_requests.py
import asyncio

from database import requests as r
from database.models import ROLE_ADMIN, ROLE_CLIENT

ADMIN_A = 111
ADMIN_B = 222
CLIENT = 500


async def _new_ticket(description: str = "Описание проблемы") -> int:
    ticket = await r.create_ticket(CLIENT, "🏠 ЖКХ", description, None)
    return ticket.id


async def test_get_or_create_user_creates_and_updates_username():
    user = await r.get_or_create_user(CLIENT, "old")
    assert user.role == ROLE_CLIENT
    await r.get_or_create_user(CLIENT, "new")
    assert (await r.get_user(CLIENT)).username == "new"


async def test_admin_ids_follow_role_changes():
    await r.get_or_create_user(ADMIN_A, "a")
    assert await r.get_admin_ids() == []
    await r.set_user_role(ADMIN_A, ROLE_ADMIN)
    assert await r.get_admin_ids() == [ADMIN_A]
    await r.set_user_role(ADMIN_A, ROLE_CLIENT)
    assert await r.get_admin_ids() == []


async def test_take_ticket_race_only_one_admin_wins():
    ticket_id = await _new_ticket()
    results = await asyncio.gather(
        r.take_ticket(ticket_id, ADMIN_A),
        r.take_ticket(ticket_id, ADMIN_B),
    )
    assert sorted(results) == [False, True]
    ticket = await r.get_ticket(ticket_id)
    assert ticket.status == "in_progress"
    assert ticket.admin_tg_id in (ADMIN_A, ADMIN_B)


async def test_take_ticket_twice_second_fails():
    ticket_id = await _new_ticket()
    assert await r.take_ticket(ticket_id, ADMIN_A) is True
    assert await r.take_ticket(ticket_id, ADMIN_B) is False


async def test_close_ticket_only_by_assigned_admin():
    ticket_id = await _new_ticket()
    await r.take_ticket(ticket_id, ADMIN_A)
    assert await r.close_ticket(ticket_id, ADMIN_B, "готово", "photo") is False
    assert await r.close_ticket(ticket_id, ADMIN_A, "готово", "photo") is True
    ticket = await r.get_ticket(ticket_id)
    assert (ticket.status, ticket.admin_comment, ticket.report_photo_id) == ("done", "готово", "photo")


async def test_close_ticket_requires_in_progress():
    ticket_id = await _new_ticket()
    assert await r.close_ticket(ticket_id, ADMIN_A, "готово", "photo") is False


async def test_reject_ticket_only_when_new():
    first = await _new_ticket()
    assert await r.reject_ticket(first, ADMIN_A, "дубликат") is True
    assert await r.reject_ticket(first, ADMIN_B, "ещё раз") is False
    assert (await r.get_ticket(first)).admin_comment == "дубликат"

    second = await _new_ticket()
    await r.take_ticket(second, ADMIN_A)
    assert await r.reject_ticket(second, ADMIN_A, "поздно") is False


async def test_next_new_ticket_wraps_around():
    ids = [await _new_ticket(f"Заявка номер {i}") for i in range(3)]
    assert (await r.get_first_new_ticket()).id == ids[0]
    assert (await r.get_next_new_ticket(ids[0])).id == ids[1]
    assert (await r.get_next_new_ticket(ids[2])).id == ids[0]  # по кругу


async def test_next_new_ticket_none_when_only_current():
    ticket_id = await _new_ticket()
    assert await r.get_next_new_ticket(ticket_id) is None


async def test_in_progress_and_closed_lists():
    a = await _new_ticket()
    b = await _new_ticket()
    c = await _new_ticket()
    await r.take_ticket(a, ADMIN_A)
    await r.take_ticket(b, ADMIN_B)
    await r.close_ticket(b, ADMIN_B, "ок", "p")
    await r.reject_ticket(c, ADMIN_A, "нет")
    assert [t.id for t in await r.get_admin_in_progress(ADMIN_A)] == [a]
    assert {t.id for t in await r.get_closed_tickets()} == {b, c}


async def test_stats_counts_all_statuses():
    assert await r.get_stats() == {"new": 0, "in_progress": 0, "done": 0, "rejected": 0}
    a, b, c, _ = [await _new_ticket() for _ in range(4)]
    await r.take_ticket(a, ADMIN_A)
    await r.take_ticket(b, ADMIN_A)
    await r.close_ticket(b, ADMIN_A, "ок", "p")
    await r.reject_ticket(c, ADMIN_A, "нет")
    assert await r.get_stats() == {"new": 1, "in_progress": 1, "done": 1, "rejected": 1}


async def test_user_tickets_newest_first_with_limit():
    ids = [await _new_ticket(f"Заявка номер {i}") for i in range(7)]
    result = await r.get_user_tickets(CLIENT, limit=5)
    assert [t.id for t in result] == list(reversed(ids))[:5]
