"""Domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotConfig:
    num_questions: int
    shuffle_questions: bool
    shuffle_options: bool
    question_timeout: int
