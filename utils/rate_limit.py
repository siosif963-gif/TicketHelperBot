# bot/utils/rate_limit.py
import time
from collections.abc import Callable


class AttemptLimiter:
    """Блокирует пользователя на lock_seconds после max_attempts неудачных попыток."""

    def __init__(
        self,
        max_attempts: int = 5,
        lock_seconds: int = 300,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_attempts = max_attempts
        self.lock_seconds = lock_seconds
        self._clock = clock
        self._failures: dict[int, int] = {}
        self._locked_until: dict[int, float] = {}

    def seconds_left(self, user_id: int) -> int:
        """Сколько секунд осталось до конца блокировки (0 — не заблокирован)."""
        until = self._locked_until.get(user_id)
        if until is None:
            return 0
        left = until - self._clock()
        if left <= 0:
            self._locked_until.pop(user_id, None)
            self._failures.pop(user_id, None)
            return 0
        return int(left) + 1

    def register_failure(self, user_id: int) -> None:
        """Учитывает неудачную попытку; при достижении лимита включает блокировку."""
        count = self._failures.get(user_id, 0) + 1
        self._failures[user_id] = count
        if count >= self.max_attempts:
            self._locked_until[user_id] = self._clock() + self.lock_seconds

    def reset(self, user_id: int) -> None:
        """Сбрасывает счётчик после успешного входа."""
        self._failures.pop(user_id, None)
        self._locked_until.pop(user_id, None)
