import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "roadsense.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the users table if it doesn't exist yet. Safe to call on every boot."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    UNIQUE NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            name          TEXT    NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def create_user(username, email, name, password):
    """Returns (success, error_message). Enforces uniqueness on username and email."""
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, email, name, generate_password_hash(password), datetime.now().isoformat()),
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        msg = str(e)
        if "username" in msg:
            return False, "That username is already taken."
        if "email" in msg:
            return False, "An account with that email already exists."
        return False, "Could not create the account."
    finally:
        conn.close()


def verify_user(username_or_email, password):
    """Look up by username OR email, then check the password hash.
    Returns the user row on success, None otherwise."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? OR email = ?",
        (username_or_email, username_or_email),
    ).fetchone()
    conn.close()

    if row and check_password_hash(row["password_hash"], password):
        return row
    return None


def get_user(username):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row


def user_count():
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    conn.close()
    return n
