import sqlite3
from datetime import datetime
from contextlib import contextmanager

@contextmanager
def db_connection():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def drop_db():
    with db_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS users")
        conn.execute("DROP TABLE IF EXISTS answers_stats")
        conn.commit()

def init_db():
    with db_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            score INTEGER DEFAULT 100,
            requests_today INTEGER DEFAULT 0,
            last_request_date TEXT
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS answers_stats (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            correct_cnt INTEGER DEFAULT 0,
            wrong_cnt INTEGER DEFAULT 0
        )
        """)
        conn.commit()


def increment_correct(name):
    with db_connection() as conn:
        cur = conn.cursor()
        # Убедимся, что запись существует
        cur.execute("SELECT * FROM answers_stats WHERE name = ?", (name,))
        if not cur.fetchone():
            cur.execute("INSERT INTO answers_stats (name, correct_cnt, wrong_cnt) VALUES (?, 1, 0)", (name,))
        else:
            cur.execute("UPDATE answers_stats SET correct_cnt = correct_cnt + 1 WHERE name = ?", (name,))
        conn.commit()

def increment_wrong(name):
    with db_connection() as conn:
        cur = conn.cursor()
        # Убедимся, что запись существует
        cur.execute("SELECT * FROM answers_stats WHERE name = ?", (name,))
        if not cur.fetchone():
            cur.execute("INSERT INTO answers_stats (name, correct_cnt, wrong_cnt) VALUES (?, 0, 1)", (name,))
        else:
            cur.execute("UPDATE answers_stats SET wrong_cnt = wrong_cnt + 1 WHERE name = ?", (name,))
        conn.commit()

def get_stats(name):
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT correct_cnt, wrong_cnt FROM answers_stats WHERE name = ?", (name,))
        row = cur.fetchone()
        return dict(row) if row else {"correct_cnt": 0, "wrong_cnt": 0}

def get_top_strategies(limit=4):
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT name, correct_cnt, wrong_cnt, (correct_cnt + wrong_cnt) as total
            FROM answers_stats
            WHERE name != 'none'
            ORDER BY total DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]

def register_user_request(user_id):
    today = datetime.now().date().isoformat()
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT last_request_date FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            if row["last_request_date"] != today:
                # Новый день — сбрасываем счётчик
                cur.execute(
                    "UPDATE users SET requests_today = 1, last_request_date = ? WHERE id = ?",
                    (today, user_id)
                )
            else:
                # Увеличиваем счётчик
                cur.execute(
                    "UPDATE users SET requests_today = requests_today + 1 WHERE id = ?",
                    (user_id,)
                )
        conn.commit()

def get_or_create_user(user_id, username):
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users (id, username, score, last_request_date) VALUES (?, ?, ?, ?)",
                (user_id, username, 100, datetime.now().date().isoformat())
            )
        else:
            cur.execute("UPDATE users SET username = ? WHERE id = ?", (username, user_id))
        conn.commit()

def can_user_request(user_id, max_attempts=100):
    today = datetime.now().date().isoformat()
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT requests_today, last_request_date FROM users WHERE id = ?", (user_id,))
        data = cur.fetchone()

        if not data:
            # Новый пользователь, может сделать все попытки
            return max_attempts

        if data["last_request_date"] != today:
            # Новый день, сбрасываем счётчик попыток
            return max_attempts

        remaining = max_attempts - data["requests_today"]
        if remaining > 0:
            return remaining
        else:
            return 0  # Лимит исчерпан


def update_score(user_id, delta):
    with db_connection() as conn:
        conn.execute("UPDATE users SET score = score + ? WHERE id = ?", (delta, user_id))
        conn.commit()

def get_score(user_id):
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT score FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return row["score"] if row else 0


def get_top_players(limit=3):
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT username, score FROM users ORDER BY score DESC LIMIT ?", (limit,))
        return [{'username': row['username'], 'score': row['score']} for row in cur.fetchall()]

def get_user_position(user_id):
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, score FROM users ORDER BY score DESC")
        users = cur.fetchall()
        for idx, row in enumerate(users, start=1):
            if row['id'] == user_id:
                return idx, row['score']
        return len(users) + 1, 0


# db.py
def get_user_requests_today(user_id):
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT requests_today FROM users WHERE id = ?", (user_id,))
        data = cur.fetchone()
        return data["requests_today"] if data else 0

# db.py (дополнение)
def get_full_rating():
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, score FROM users ORDER BY score DESC")
        return [dict(row) for row in cur.fetchall()]