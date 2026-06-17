"""Question helpers."""

from __future__ import annotations

import random

from telegram.constants import PollLimit


def shuffle_options_for_poll(
    options: list[str],
    correct_option_index: int,
) -> tuple[list[str], int]:
    indexed = list(enumerate(options))
    random.shuffle(indexed)
    shuffled = [text for _, text in indexed]
    mapped_correct = next(
        index
        for index, (original_index, _) in enumerate(indexed)
        if original_index == correct_option_index
    )
    return shuffled, mapped_correct


def format_numbered_question(question_text: str, index: int, total: int) -> str:
    prefix = f"Question {index + 1}/{total}: "
    normalized = " ".join(str(question_text or "").split()) or "Question"
    limit = int(PollLimit.MAX_QUESTION_LENGTH)
    if len(prefix) + len(normalized) <= limit:
        return f"{prefix}{normalized}"

    available = max(1, limit - len(prefix))
    if available <= 3:
        return f"{prefix}{normalized[:available]}"
    return f"{prefix}{normalized[: available - 3].rstrip()}..."
