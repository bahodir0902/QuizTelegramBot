"""JSON helpers."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def parse_json_int_list(raw: str | None) -> list[int]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid question_ids_json payload")
        return []
    if not isinstance(data, list):
        return []
    values: list[int] = []
    for item in data:
        try:
            values.append(int(item))
        except (TypeError, ValueError):
            continue
    return values


def parse_options_json(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Invalid options_json in database") from exc
    if not isinstance(data, list) or len(data) < 2:
        raise ValueError("options_json must be a list with at least 2 items")
    return [str(item) for item in data]
