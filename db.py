import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

DB_PATH = "users.db"


@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    with db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_active_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_answers (
                user_id INTEGER NOT NULL,
                question_id TEXT NOT NULL,
                selected_option TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                answered_at TEXT NOT NULL,
                PRIMARY KEY (user_id, question_id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        conn.commit()


def get_or_create_user(user_id: int, username: str) -> None:
    now = utc_now_iso()
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if cur.fetchone() is None:
            cur.execute(
                """
                INSERT INTO users (id, username, score, created_at, last_active_at)
                VALUES (?, ?, 0, ?, ?)
                """,
                (user_id, username, now, now),
            )
        else:
            cur.execute(
                "UPDATE users SET username = ?, last_active_at = ? WHERE id = ?",
                (username, now, user_id),
            )
        conn.commit()


def touch_user(user_id: int) -> None:
    with db_connection() as conn:
        conn.execute(
            "UPDATE users SET last_active_at = ? WHERE id = ?",
            (utc_now_iso(), user_id),
        )
        conn.commit()


def get_user_summary(user_id: int) -> Optional[Dict[str, int]]:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, score FROM users WHERE id = ?",
            (user_id,),
        )
        user_row = cur.fetchone()
        if user_row is None:
            return None

        cur.execute(
            """
            SELECT
                COUNT(*) AS answered_total,
                COALESCE(SUM(is_correct), 0) AS correct_total
            FROM quiz_answers
            WHERE user_id = ?
            """,
            (user_id,),
        )
        stat_row = cur.fetchone()

        return {
            "id": user_row["id"],
            "username": user_row["username"],
            "score": user_row["score"],
            "answered_total": stat_row["answered_total"],
            "correct_total": stat_row["correct_total"],
        }


def record_answer(
    user_id: int,
    question_id: str,
    selected_option: str,
    is_correct: bool,
    correct_points: int = 2,
    wrong_points: int = 0,
) -> Tuple[bool, int]:
    """
    Returns tuple (is_new_answer, new_score).
    """
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT is_correct FROM quiz_answers WHERE user_id = ? AND question_id = ?",
            (user_id, question_id),
        )
        existing = cur.fetchone()

        if existing is not None:
            cur.execute("SELECT score FROM users WHERE id = ?", (user_id,))
            score_row = cur.fetchone()
            return False, score_row["score"] if score_row else 0

        now = utc_now_iso()
        cur.execute(
            """
            INSERT INTO quiz_answers (user_id, question_id, selected_option, is_correct, answered_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, question_id, selected_option, int(is_correct), now),
        )

        delta = correct_points if is_correct else wrong_points
        cur.execute("UPDATE users SET score = score + ?, last_active_at = ? WHERE id = ?", (delta, now, user_id))

        cur.execute("SELECT score FROM users WHERE id = ?", (user_id,))
        new_score = cur.fetchone()["score"]
        conn.commit()
        return True, new_score


def get_answered_question_ids(user_id: int) -> List[str]:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT question_id FROM quiz_answers WHERE user_id = ? ORDER BY answered_at",
            (user_id,),
        )
        return [row["question_id"] for row in cur.fetchall()]


def get_leaderboard(limit: int = 10) -> List[Dict[str, int]]:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                u.id,
                u.username,
                u.score,
                COALESCE(SUM(qa.is_correct), 0) AS correct_total
            FROM users u
            LEFT JOIN quiz_answers qa ON qa.user_id = u.id
            GROUP BY u.id, u.username, u.score
            ORDER BY u.score DESC, correct_total DESC, u.last_active_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_user_rank(user_id: int) -> Optional[int]:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id
            FROM users
            ORDER BY score DESC, last_active_at DESC
            """
        )
        for idx, row in enumerate(cur.fetchall(), start=1):
            if row["id"] == user_id:
                return idx
        return None
