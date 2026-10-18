# bot/tests/conftest.py
import os
import tempfile

# Переменные окружения нужно задать ДО импорта config/engine.
_tmp_dir = tempfile.mkdtemp(prefix="ticketbot_tests_")
os.environ["BOT_TOKEN"] = "1:test-token"
os.environ["ADMIN_PASSWORD_HASH"] = "03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4"
os.environ["DB_URL"] = f"sqlite+aiosqlite:///{_tmp_dir}/test.db"

import pytest_asyncio  # noqa: E402

from database.engine import engine  # noqa: E402
from database.models import Base  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Пересоздаёт таблицы перед каждым тестом."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
