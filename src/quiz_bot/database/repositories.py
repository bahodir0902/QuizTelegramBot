"""Raw SQL repository helpers."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from quiz_bot.domain import BotConfig


def _load_options(options_json: str) -> list[str]:
    data = json.loads(options_json)
    if not isinstance(data, list):
        raise ValueError("options_json must be a list")
    return [str(item) for item in data]


def _validate_options(options: list[str], correct_option_index: int) -> None:
    if len(options) < 2:
        raise ValueError("A question needs at least two options")
    if correct_option_index < 0 or correct_option_index >= len(options):
        raise ValueError("Correct option index is out of range")


def row_to_config(row: sqlite3.Row) -> BotConfig:
    return BotConfig(
        num_questions=int(row["num_questions"]),
        shuffle_questions=bool(int(row["shuffle_questions"])),
        shuffle_options=bool(int(row["shuffle_options"])),
        question_timeout=int(row["question_timeout"]),
    )


def read_config(conn: sqlite3.Connection) -> BotConfig:
    row = conn.execute("SELECT * FROM configs WHERE id = 1").fetchone()
    if row is None:
        raise RuntimeError("configs row missing")
    return row_to_config(row)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_db_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def _parse_db_timestamp(raw: object) -> datetime | None:
    if raw in (None, ""):
        return None
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_admin_user(conn: sqlite3.Connection, user_id: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM admins WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        is not None
    )


def upsert_user_db(
    conn: sqlite3.Connection,
    user_id: int,
    username: str | None,
    full_name: str,
    language_code: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO user_progress (user_id, username, full_name, language_code)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            full_name = CASE
                WHEN user_progress.first_name IS NOT NULL THEN user_progress.full_name
                ELSE excluded.full_name
            END
        """,
        (user_id, username, full_name, language_code),
    )


def get_user_progress_db(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM user_progress WHERE user_id = ?",
        (user_id,),
    ).fetchone()


def set_user_language_db(conn: sqlite3.Connection, user_id: int, language_code: str) -> None:
    conn.execute(
        "UPDATE user_progress SET language_code = ? WHERE user_id = ?",
        (language_code, user_id),
    )


def set_onboarding_step_db(conn: sqlite3.Connection, user_id: int, step: str) -> None:
    conn.execute(
        """
        UPDATE user_progress
        SET onboarding_step = ?,
            onboarding_completed = 0
        WHERE user_id = ?
        """,
        (step, user_id),
    )


def save_onboarding_name_db(
    conn: sqlite3.Connection,
    user_id: int,
    first_name: str,
    last_name: str,
) -> None:
    full_name = f"{first_name} {last_name}".strip()
    conn.execute(
        """
        UPDATE user_progress
        SET first_name = ?,
            last_name = ?,
            full_name = ?,
            onboarding_step = 'age',
            onboarding_completed = 0
        WHERE user_id = ?
        """,
        (first_name, last_name, full_name, user_id),
    )


def save_onboarding_age_db(conn: sqlite3.Connection, user_id: int, age: int) -> None:
    conn.execute(
        """
        UPDATE user_progress
        SET age = ?,
            onboarding_step = 'region',
            onboarding_completed = 0
        WHERE user_id = ?
        """,
        (age, user_id),
    )


def complete_onboarding_db(conn: sqlite3.Connection, user_id: int, region: str) -> sqlite3.Row:
    conn.execute(
        """
        UPDATE user_progress
        SET region = ?,
            onboarding_completed = 1,
            onboarding_step = NULL,
            onboarded_at = ?
        WHERE user_id = ?
        """,
        (region, _to_db_timestamp(_utc_now()), user_id),
    )
    row = get_user_progress_db(conn, user_id)
    if row is None:
        raise RuntimeError("user_progress row missing after onboarding completion")
    return row


def get_user_by_poll_id_db(conn: sqlite3.Connection, poll_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM user_progress WHERE current_poll_id = ?",
        (poll_id,),
    ).fetchone()


def insert_question_db(
    conn: sqlite3.Connection,
    question_text: str,
    options: list[str],
    correct_option_index: int,
) -> None:
    _validate_options(options, correct_option_index)
    conn.execute(
        """
        INSERT INTO questions (question_text, options_json, correct_option_index)
        VALUES (?, ?, ?)
        """,
        (
            question_text,
            json.dumps(options, ensure_ascii=False),
            correct_option_index,
        ),
    )


def list_questions_db(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT id, question_text, correct_option_index
            FROM questions
            ORDER BY id ASC
            """
        ).fetchall()
    )


def update_question_text_db(
    conn: sqlite3.Connection,
    question_id: int,
    question_text: str,
) -> bool:
    cursor = conn.execute(
        "UPDATE questions SET question_text = ? WHERE id = ?",
        (question_text, question_id),
    )
    return cursor.rowcount == 1


def replace_question_options_db(
    conn: sqlite3.Connection,
    question_id: int,
    options: list[str],
    correct_option_index: int,
) -> bool:
    _validate_options(options, correct_option_index)
    cursor = conn.execute(
        """
        UPDATE questions
        SET options_json = ?, correct_option_index = ?
        WHERE id = ?
        """,
        (
            json.dumps(options, ensure_ascii=False),
            correct_option_index,
            question_id,
        ),
    )
    return cursor.rowcount == 1


def update_question_correct_index_db(
    conn: sqlite3.Connection,
    question_id: int,
    correct_option_index: int,
) -> bool:
    row = fetch_question_db(conn, question_id)
    if row is None:
        return False
    options = _load_options(str(row["options_json"]))
    _validate_options(options, correct_option_index)
    cursor = conn.execute(
        "UPDATE questions SET correct_option_index = ? WHERE id = ?",
        (correct_option_index, question_id),
    )
    return cursor.rowcount == 1


def delete_question_db(conn: sqlite3.Connection, question_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM questions WHERE id = ?",
        (question_id,),
    )
    return cursor.rowcount == 1


def delete_question_option_db(
    conn: sqlite3.Connection,
    question_id: int,
    option_index: int,
) -> tuple[bool, str]:
    row = fetch_question_db(conn, question_id)
    if row is None:
        return False, "missing_question"
    options = _load_options(str(row["options_json"]))
    if option_index < 0 or option_index >= len(options):
        return False, "invalid_option"
    if len(options) <= 2:
        return False, "minimum_options"

    correct_index = int(row["correct_option_index"])
    options.pop(option_index)
    if option_index == correct_index:
        correct_index = 0
    elif option_index < correct_index:
        correct_index -= 1

    replace_question_options_db(conn, question_id, options, correct_index)
    return True, "ok"


def fetch_question_stats_db(conn: sqlite3.Connection, question_id: int) -> dict[str, object] | None:
    row = fetch_question_db(conn, question_id)
    if row is None:
        return None

    summary = conn.execute(
        """
        SELECT
            COUNT(id) AS attempts,
            COALESCE(SUM(CASE WHEN timed_out = 0 THEN 1 ELSE 0 END), 0) AS answered,
            COALESCE(SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END), 0) AS correct,
            COALESCE(SUM(CASE WHEN timed_out = 1 THEN 1 ELSE 0 END), 0) AS timed_out
        FROM question_answers
        WHERE question_id = ?
        """,
        (question_id,),
    ).fetchone()
    option_rows = conn.execute(
        """
        SELECT selected_option_index, COUNT(*) AS selected_count
        FROM question_answers
        WHERE question_id = ?
            AND timed_out = 0
            AND selected_option_index IS NOT NULL
        GROUP BY selected_option_index
        """,
        (question_id,),
    ).fetchall()
    option_counts = {
        int(option_row["selected_option_index"]): int(option_row["selected_count"])
        for option_row in option_rows
    }
    return {
        "question": row,
        "attempts": int(summary["attempts"]),
        "answered": int(summary["answered"]),
        "correct": int(summary["correct"]),
        "timed_out": int(summary["timed_out"]),
        "option_counts": option_counts,
    }


def update_config_field_db(conn: sqlite3.Connection, column: str, value: int) -> None:
    allowed = {
        "num_questions",
        "shuffle_questions",
        "shuffle_options",
        "question_timeout",
    }
    if column not in allowed:
        raise ValueError(f"Invalid config column: {column}")
    conn.execute(f"UPDATE configs SET {column} = ? WHERE id = 1", (value,))


def fetch_leaderboard_db(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT username, full_name, score
            FROM user_progress
            ORDER BY score DESC, full_name ASC
            """
        ).fetchall()
    )


def fetch_export_rows_db(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT
                username,
                full_name,
                first_name,
                last_name,
                age,
                region,
                score,
                last_duration_seconds
            FROM user_progress
            ORDER BY score DESC
            """
        ).fetchall()
    )


def save_quiz_pool_db(conn: sqlite3.Connection, user_id: int, question_ids: list[int]) -> None:
    conn.execute(
        """
        UPDATE user_progress SET
            question_ids_json = ?,
            current_pool_index = 0,
            score = 0,
            current_poll_id = NULL,
            current_correct_index = NULL,
            current_question_id = NULL,
            current_option_order_json = NULL,
            session_status = 'active',
            start_time = ?,
            finished_time = NULL,
            last_duration_seconds = NULL
        WHERE user_id = ?
        """,
        (
            json.dumps(question_ids),
            _to_db_timestamp(_utc_now()),
            user_id,
        ),
    )


def update_poll_state_db(
    conn: sqlite3.Connection,
    user_id: int,
    poll_id: str,
    correct_index: int,
    question_id: int,
    option_order: list[int],
) -> None:
    conn.execute(
        """
        UPDATE user_progress SET
            current_poll_id = ?,
            current_correct_index = ?,
            current_question_id = ?,
            current_option_order_json = ?,
            session_status = 'active'
        WHERE user_id = ?
        """,
        (
            poll_id,
            correct_index,
            question_id,
            json.dumps(option_order),
            user_id,
        ),
    )


def increment_score_and_advance_db(
    conn: sqlite3.Connection,
    user_id: int,
    was_correct: bool,
    expected_poll_id: str | None = None,
) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM user_progress WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError("user_progress row missing")
    if expected_poll_id is not None and row["current_poll_id"] != expected_poll_id:
        raise RuntimeError("poll_state_mismatch")

    new_score = int(row["score"]) + (1 if was_correct else 0)
    new_index = int(row["current_pool_index"]) + 1
    conn.execute(
        """
        UPDATE user_progress SET
            score = ?,
            current_pool_index = ?,
            current_poll_id = NULL,
            current_correct_index = NULL,
            current_question_id = NULL,
            current_option_order_json = NULL,
            session_status = CASE
                WHEN question_ids_json IS NULL THEN 'idle'
                ELSE session_status
            END
        WHERE user_id = ?
        """,
        (new_score, new_index, user_id),
    )
    updated = conn.execute(
        "SELECT * FROM user_progress WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if updated is None:
        raise RuntimeError("user_progress row missing after update")
    return updated


def advance_timeout_poll_db(
    conn: sqlite3.Connection,
    poll_id: str,
    user_id: int,
) -> tuple[sqlite3.Row | None, str]:
    row = conn.execute(
        """
        SELECT * FROM user_progress
        WHERE user_id = ? AND current_poll_id = ?
        """,
        (user_id, poll_id),
    ).fetchone()
    if row is None:
        return None, "stale_poll"

    new_index = int(row["current_pool_index"]) + 1
    question_id = row["current_question_id"]
    if question_id is not None:
        conn.execute(
            """
            INSERT INTO question_answers (
                question_id, user_id, poll_id, selected_option_index, was_correct, timed_out
            )
            SELECT ?, ?, ?, NULL, 0, 1
            WHERE EXISTS (SELECT 1 FROM questions WHERE id = ?)
            ON CONFLICT(poll_id) DO NOTHING
            """,
            (int(question_id), user_id, poll_id, int(question_id)),
        )
    cursor = conn.execute(
        """
        UPDATE user_progress SET
            current_pool_index = ?,
            current_poll_id = NULL,
            current_correct_index = NULL,
            current_question_id = NULL,
            current_option_order_json = NULL
        WHERE user_id = ? AND current_poll_id = ?
        """,
        (new_index, user_id, poll_id),
    )
    if cursor.rowcount != 1:
        return None, "stale_poll"

    updated = conn.execute(
        "SELECT * FROM user_progress WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if updated is None:
        raise RuntimeError("user_progress row missing after timeout advance")
    return updated, "ok"


def score_poll_answer_db(
    conn: sqlite3.Connection,
    poll_id: str,
    answer_user_id: int,
    selected_option_id: int,
) -> tuple[sqlite3.Row | None, str]:
    row = conn.execute(
        "SELECT * FROM user_progress WHERE current_poll_id = ?",
        (poll_id,),
    ).fetchone()
    if row is None:
        return None, "missing_poll"

    bound_user_id = int(row["user_id"])
    if bound_user_id != answer_user_id:
        return None, "user_mismatch"

    correct_index = row["current_correct_index"]
    if correct_index is None:
        return None, "missing_correct_index"

    was_correct = selected_option_id == int(correct_index)
    question_id = row["current_question_id"]
    option_order_json = row["current_option_order_json"]
    selected_original_index = selected_option_id
    if option_order_json is not None:
        try:
            option_order = json.loads(str(option_order_json))
            if isinstance(option_order, list):
                selected_original_index = int(option_order[selected_option_id])
        except (IndexError, TypeError, ValueError, json.JSONDecodeError):
            selected_original_index = selected_option_id

    if question_id is not None:
        conn.execute(
            """
            INSERT INTO question_answers (
                question_id, user_id, poll_id, selected_option_index, was_correct, timed_out
            )
            SELECT ?, ?, ?, ?, ?, 0
            WHERE EXISTS (SELECT 1 FROM questions WHERE id = ?)
            ON CONFLICT(poll_id) DO NOTHING
            """,
            (
                int(question_id),
                bound_user_id,
                poll_id,
                selected_original_index,
                1 if was_correct else 0,
                int(question_id),
            ),
        )

    new_score = int(row["score"]) + (1 if was_correct else 0)
    new_index = int(row["current_pool_index"]) + 1
    cursor = conn.execute(
        """
        UPDATE user_progress SET
            score = ?,
            current_pool_index = ?,
            current_poll_id = NULL,
            current_correct_index = NULL,
            current_question_id = NULL,
            current_option_order_json = NULL
        WHERE user_id = ? AND current_poll_id = ?
        """,
        (new_score, new_index, bound_user_id, poll_id),
    )
    if cursor.rowcount != 1:
        return None, "stale_poll"

    updated = conn.execute(
        "SELECT * FROM user_progress WHERE user_id = ?",
        (bound_user_id,),
    ).fetchone()
    if updated is None:
        raise RuntimeError("user_progress row missing after scoring")
    return updated, "ok"


def clear_active_poll_db(
    conn: sqlite3.Connection,
    user_id: int,
    session_status: str = "idle",
) -> None:
    conn.execute(
        """
        UPDATE user_progress SET
            current_poll_id = NULL,
            current_correct_index = NULL,
            current_question_id = NULL,
            current_option_order_json = NULL,
            session_status = ?
        WHERE user_id = ?
        """,
        (session_status, user_id),
    )


def complete_quiz_session_db(
    conn: sqlite3.Connection,
    user_id: int,
    finished_at: datetime | None = None,
) -> sqlite3.Row:
    row = get_user_progress_db(conn, user_id)
    if row is None:
        raise RuntimeError("user_progress row missing")
    if row["session_status"] == "completed" and row["last_duration_seconds"] is not None:
        return row

    finished = (finished_at or _utc_now()).astimezone(UTC)
    started = _parse_db_timestamp(row["start_time"]) or finished
    duration_seconds = max(0, int((finished - started).total_seconds()))

    conn.execute(
        """
        UPDATE user_progress SET
            current_poll_id = NULL,
            current_correct_index = NULL,
            session_status = 'completed',
            finished_time = ?,
            last_duration_seconds = ?
        WHERE user_id = ?
        """,
        (_to_db_timestamp(finished), duration_seconds, user_id),
    )
    updated = get_user_progress_db(conn, user_id)
    if updated is None:
        raise RuntimeError("user_progress row missing after quiz completion")
    return updated


def build_question_pool_db(conn: sqlite3.Connection, config: BotConfig) -> list[int]:
    if config.shuffle_questions:
        rows = conn.execute("SELECT id FROM questions ORDER BY RANDOM()").fetchall()
    else:
        rows = conn.execute("SELECT id FROM questions ORDER BY id ASC").fetchall()
    ids = [int(row["id"]) for row in rows]
    return ids[: min(len(ids), config.num_questions)]


def fetch_question_db(conn: sqlite3.Connection, question_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM questions WHERE id = ?",
        (question_id,),
    ).fetchone()


def count_questions_db(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"])


def toggle_config_field_db(conn: sqlite3.Connection, column: str) -> BotConfig:
    config = read_config(conn)
    if column == "shuffle_questions":
        new_value = 0 if config.shuffle_questions else 1
    elif column == "shuffle_options":
        new_value = 0 if config.shuffle_options else 1
    else:
        raise ValueError(f"Cannot toggle config column: {column}")
    update_config_field_db(conn, column, new_value)
    return read_config(conn)


def mark_session_status_db(conn: sqlite3.Connection, user_id: int, status: str) -> None:
    conn.execute(
        "UPDATE user_progress SET session_status = ? WHERE user_id = ?",
        (status, user_id),
    )


def seed_admin_db(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
        (user_id,),
    )
