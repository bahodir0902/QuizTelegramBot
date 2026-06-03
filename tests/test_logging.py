"""Logging filter tests."""

from __future__ import annotations

import logging
import unittest

from quiz_bot.config.logging import SensitiveDataFilter


class SensitiveDataFilterTests(unittest.TestCase):
    def test_numeric_log_args_remain_integers(self) -> None:
        token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Seeded %d admin(s)",
            args=(2,),
            exc_info=None,
        )
        SensitiveDataFilter(token).filter(record)
        self.assertEqual(record.args, (2,))
        self.assertEqual(record.getMessage(), "Seeded 2 admin(s)")

    def test_string_args_are_masked(self) -> None:
        token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Token=%s",
            args=(token,),
            exc_info=None,
        )
        SensitiveDataFilter(token).filter(record)
        self.assertEqual(record.args, ("***TG_BOT_TOKEN***",))


if __name__ == "__main__":
    unittest.main()
