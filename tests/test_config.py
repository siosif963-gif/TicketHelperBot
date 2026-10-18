# bot/tests/test_config.py
import pytest

from config import parse_admin_ids, parse_bool


def test_parse_admin_ids():
    assert parse_admin_ids(None) == frozenset()
    assert parse_admin_ids("  ") == frozenset()
    assert parse_admin_ids("1, 2,3,") == frozenset({1, 2, 3})


def test_parse_admin_ids_rejects_garbage():
    with pytest.raises(RuntimeError):
        parse_admin_ids("1,abc")


@pytest.mark.parametrize("raw,expected", [("true", True), ("1", True), ("No", False), ("", True), (None, True)])
def test_parse_bool_default_true(raw, expected):
    assert parse_bool(raw, default=True) is expected
