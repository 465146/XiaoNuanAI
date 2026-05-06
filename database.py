import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager
from typing import Optional

DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "123456789s",
    "database": "cbt_xiaonuan",
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
    "autocommit": True,
}


@contextmanager
def get_db():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


# ── Users ──

def create_user(username: str, password_hash: str) -> int:
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash),
            )
            return cur.lastrowid


def get_user_by_username(username: str) -> Optional[dict]:
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE username = %s",
                (username,),
            )
            return cur.fetchone()


# ── Messages ──

def save_message(user_id: int, role: str, content: str):
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)",
                (user_id, role, content),
            )


def get_messages(user_id: int, limit: int = 100) -> list[dict]:
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "SELECT role, content, created_at FROM messages "
                "WHERE user_id = %s ORDER BY id ASC LIMIT %s",
                (user_id, limit),
            )
            return cur.fetchall()


def clear_messages(user_id: int):
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute("DELETE FROM messages WHERE user_id = %s", (user_id,))


# ── Daily Scores ──

def save_daily_score(user_id: int, date: str, score: float, note: str = ""):
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO daily_scores (user_id, date, score, note) VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE score = GREATEST(score, VALUES(score)), "
                "note = CONCAT(note, '; ', VALUES(note))",
                (user_id, date, score, note),
            )


def get_daily_scores(user_id: int, days: int = 30) -> list[dict]:
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "SELECT date, score, note FROM daily_scores "
                "WHERE user_id = %s AND date >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
                "ORDER BY date ASC",
                (user_id, days),
            )
            return cur.fetchall()


# ── PHQ-9 Records ──

def save_phq9_record(user_id: int, total_score: int, severity: str, q9_score: int, note: str = ""):
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO phq9_records (user_id, total_score, severity, q9_score, note) "
                "VALUES (%s, %s, %s, %s, %s)",
                (user_id, total_score, severity, q9_score, note),
            )


def get_phq9_history(user_id: int, limit: int = 20) -> list[dict]:
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, total_score, severity, q9_score, note, created_at "
                "FROM phq9_records WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            )
            return cur.fetchall()


# ── Diary ──

def save_diary(user_id: int, date: str, content: str, mood: str = ""):
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO diary_entries (user_id, date, content, mood) VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE content = VALUES(content), mood = VALUES(mood)",
                (user_id, date, content, mood),
            )


def get_diary_list(user_id: int, limit: int = 30) -> list[dict]:
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "SELECT date, mood, LEFT(content, 100) AS preview FROM diary_entries "
                "WHERE user_id = %s ORDER BY date DESC LIMIT %s",
                (user_id, limit),
            )
            return cur.fetchall()


def get_diary(user_id: int, date: str) -> Optional[dict]:
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "SELECT date, mood, content, created_at FROM diary_entries "
                "WHERE user_id = %s AND date = %s",
                (user_id, date),
            )
            return cur.fetchone()


# ── Verify Codes ──

def save_verify_code(email: str, code: str, expires: "datetime"):
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO verify_codes (email, code, expires_at) VALUES (%s, %s, %s)",
                (email, code, expires),
            )


def check_verify_code(email: str, code: str) -> bool:
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id FROM verify_codes "
                "WHERE email = %s AND code = %s AND used = 0 AND expires_at > NOW() "
                "ORDER BY id DESC LIMIT 1",
                (email, code),
            )
            return cur.fetchone() is not None


def mark_code_used(email: str, code: str):
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "UPDATE verify_codes SET used = 1 WHERE email = %s AND code = %s",
                (email, code),
            )


def update_user_email(user_id: int, email: str):
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "UPDATE users SET email = %s, email_verified = 1 WHERE id = %s",
                (email, user_id),
            )


# ── WeChat Bots (per-user) ──

def save_wechat_bot(user_id: int, bot_token: str, bot_id: str, wechat_user_id: str = "", base_url: str = ""):
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO wechat_bots (user_id, bot_token, bot_id, wechat_user_id, base_url) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "bot_token = VALUES(bot_token), wechat_user_id = VALUES(wechat_user_id), "
                "base_url = VALUES(base_url)",
                (user_id, bot_token, bot_id, wechat_user_id, base_url),
            )


def get_wechat_bot(user_id: int) -> dict | None:
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "SELECT bot_id, bot_token, wechat_user_id, base_url, connected_at "
                "FROM wechat_bots WHERE user_id = %s ORDER BY id DESC LIMIT 1",
                (user_id,),
            )
            return cur.fetchone()


# ── Config (global, not per-user) ──

def get_config(key: str) -> Optional[str]:
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute("SELECT `value` FROM config WHERE `key` = %s", (key,))
            row = cur.fetchone()
            return row["value"] if row else None


def set_config(key: str, value: str):
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO config (`key`, `value`) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)",
                (key, value),
            )
