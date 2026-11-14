"""Signal store: every signal Rex's bot forwards is also saved here, so other bots can read it."""
import os
import sqlite3
import threading
from datetime import datetime, timezone

DB_PATH = os.path.join(os.environ.get('DATA_DIR', '.'), 'signal_store.db')
_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS signals ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "source_id INTEGER, "
        "created_at TEXT NOT NULL, "
        "text TEXT NOT NULL)"
    )
    return conn


def save_signal(source_id, text):
    """Save one signal and return its store ID."""
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "INSERT INTO signals (source_id, created_at, text) VALUES (?, ?, ?)",
                (source_id, datetime.now(timezone.utc).isoformat(), text),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def _rows(sql, params):
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    return [{"id": r[0], "source_id": r[1], "created_at": r[2], "text": r[3]} for r in rows]


def list_since(after_id=0, limit=50):
    """Signals with an ID greater than after_id, oldest first."""
    return _rows(
        "SELECT id, source_id, created_at, text FROM signals WHERE id > ? ORDER BY id LIMIT ?",
        (after_id, limit),
    )


def latest(limit=20):
    """The newest signals, newest first."""
    return list(reversed(_rows(
        "SELECT id, source_id, created_at, text FROM signals ORDER BY id DESC LIMIT ?",
        (limit,),
    )))
