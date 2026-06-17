"""Question service tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from quiz_bot.services.question_service import shuffle_options_for_poll


class QuestionServiceTests(unittest.TestCase):
    def test_shuffle_options_returns_original_option_order(self) -> None:
        with patch("quiz_bot.services.question_service.random.shuffle") as shuffle:
            shuffle.side_effect = lambda indexed: indexed.reverse()

            shuffled, mapped_correct, option_order = shuffle_options_for_poll(
                ["A", "B", "C"],
                1,
            )

        self.assertEqual(shuffled, ["C", "B", "A"])
        self.assertEqual(mapped_correct, 1)
        self.assertEqual(option_order, [2, 1, 0])


if __name__ == "__main__":
    unittest.main()
