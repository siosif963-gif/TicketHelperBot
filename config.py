# bot/config.py
import hashlib
import hmac
import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str | None = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD_HASH: str | None = os.getenv("ADMIN_PASSWORD_HASH")
DB_URL: str = os.getenv("DB_URL", "sqlite+aiosqlite:///bot.db")

if not BOT_TOKEN:
    raise RuntimeError("Заполните BOT_TOKEN в .env")
if not ADMIN_PASSWORD_HASH:
    raise RuntimeError("Заполните ADMIN_PASSWORD_HASH в .env (запустите: python hash_password.py)")


def hash_password(password: str) -> str:
    """Возвращает SHA-256 хэш пароля в hex-виде."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def check_password(password: str) -> bool:
    """Сравнивает хэш введённого пароля с эталонным в постоянное время."""
    return hmac.compare_digest(hash_password(password), ADMIN_PASSWORD_HASH.strip().lower())
