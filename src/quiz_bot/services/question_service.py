"""Question helpers."""

from __future__ import annotations

import random


def shuffle_options_for_poll(
    options: list[str],
    correct_option_index: int,
) -> tuple[list[str], int, list[int]]:
    indexed = list(enumerate(options))
    random.shuffle(indexed)
    shuffled = [text for _, text in indexed]
    original_order = [original_index for original_index, _ in indexed]
    mapped_correct = next(
        index
        for index, (original_index, _) in enumerate(indexed)
        if original_index == correct_option_index
    )
    return shuffled, mapped_correct, original_order
