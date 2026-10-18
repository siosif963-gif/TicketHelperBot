# bot/config.py
import hashlib
import hmac
import os

from dotenv import load_dotenv

load_dotenv()


def parse_bool(raw: str | None, default: bool = False) -> bool:
    """Разбирает булево значение из строки окружения."""
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def parse_admin_ids(raw: str | None) -> frozenset[int]:
    """Разбирает список Telegram ID через запятую; пустая строка — пустой набор."""
    if not raw or not raw.strip():
        return frozenset()
    try:
        return frozenset(int(part) for part in raw.split(",") if part.strip())
    except ValueError:
        raise RuntimeError("ADMIN_IDS должен содержать числовые Telegram ID через запятую") from None


BOT_TOKEN: str | None = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD_HASH: str | None = os.getenv("ADMIN_PASSWORD_HASH")
DB_URL: str = os.getenv("DB_URL", "sqlite+aiosqlite:///bot.db")
# Администраторы по Telegram ID: получают доступ без PIN.
ADMIN_IDS: frozenset[int] = parse_admin_ids(os.getenv("ADMIN_IDS"))
# Демо-режим: разрешает вход в админку по PIN (удобно показывать проект).
DEMO_MODE: bool = parse_bool(os.getenv("DEMO_MODE"), default=False)

if not BOT_TOKEN:
    raise RuntimeError("Заполните BOT_TOKEN в .env")
if DEMO_MODE and not ADMIN_PASSWORD_HASH:
    raise RuntimeError(
        "Заполните ADMIN_PASSWORD_HASH в .env (python hash_password.py) или отключите DEMO_MODE"
    )
if not DEMO_MODE and not ADMIN_IDS:
    raise RuntimeError("При DEMO_MODE=false укажите администраторов в ADMIN_IDS")


def hash_password(password: str) -> str:
    """Возвращает SHA-256 хэш пароля в hex-виде."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def check_password(password: str) -> bool:
    """Сравнивает хэш введённого пароля с эталонным; вход по PIN работает только в DEMO_MODE."""
    if not DEMO_MODE or not ADMIN_PASSWORD_HASH:
        return False
    return hmac.compare_digest(hash_password(password), ADMIN_PASSWORD_HASH.strip().lower())
