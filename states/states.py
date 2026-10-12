# bot/states/states.py
from aiogram.fsm.state import State, StatesGroup


class TicketForm(StatesGroup):
    choose_category = State()
    enter_description = State()
    upload_photo = State()
    confirm = State()


class AdminAuth(StatesGroup):
    wait_admin_password = State()


class AdminProcess(StatesGroup):
    wait_admin_comment = State()
    wait_admin_photo = State()
    wait_reject_reason = State()
