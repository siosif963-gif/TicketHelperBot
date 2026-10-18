# bot/tests/test_rate_limit.py
from utils.rate_limit import AttemptLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_locks_after_max_attempts_and_unlocks_after_timeout():
    clock = FakeClock()
    limiter = AttemptLimiter(max_attempts=3, lock_seconds=60, clock=clock)
    for _ in range(2):
        limiter.register_failure(1)
    assert limiter.seconds_left(1) == 0
    limiter.register_failure(1)
    assert limiter.seconds_left(1) > 0
    clock.now += 61
    assert limiter.seconds_left(1) == 0


def test_users_are_independent_and_reset_clears():
    limiter = AttemptLimiter(max_attempts=2, lock_seconds=60, clock=FakeClock())
    limiter.register_failure(1)
    limiter.register_failure(1)
    assert limiter.seconds_left(1) > 0
    assert limiter.seconds_left(2) == 0
    limiter.reset(1)
    assert limiter.seconds_left(1) == 0
