"""
db.py — SQLite database for QnAI multi-user sessions.

Tables
──────
  users        → professors and students
  sessions     → lecture sessions (one per class / meeting)
  session_members → which users are in which session
  escalations  → confusion tags submitted by students

On first import, creates the DB and seeds dummy data.
"""

import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "qnai.db")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn() -> sqlite3.Connection:
    """Return a connection with row_factory set to dict."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ──────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL CHECK(role IN ('professor', 'student')),
    email       TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    topic       TEXT NOT NULL DEFAULT '',
    transcript  TEXT NOT NULL DEFAULT '',
    professor_id TEXT NOT NULL REFERENCES users(id),
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_members (
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    user_id     TEXT NOT NULL REFERENCES users(id),
    joined_at   TEXT NOT NULL,
    PRIMARY KEY (session_id, user_id)
);

CREATE TABLE IF NOT EXISTS escalations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    student_id  TEXT NOT NULL REFERENCES users(id),
    tag         TEXT NOT NULL,
    query       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
"""


def init_db():
    """Create tables if they don't exist."""
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Seed dummy data
# ──────────────────────────────────────────────

DUMMY_USERS = [
    ("prof-001",  "Example",      "professor", "example1@university.edu"),
    ("prof-002",  "Example2", "professor", "example2@university.edu"),
    ("stu-001",   "Alice Johnson",        "student",   "alice.j@university.edu"),
    ("stu-002",   "Bob Kim",              "student",   "bob.k@university.edu"),
    ("stu-003",   "Charlie Patel",        "student",   "charlie.p@university.edu"),
    ("stu-004",   "Diana Lopez",          "student",   "diana.l@university.edu"),
    ("stu-005",   "Ethan Brown",          "student",   "ethan.b@university.edu"),
    ("stu-006",   "Fiona Davis",          "student",   "fiona.d@university.edu"),
    ("stu-007",   "George Wilson",        "student",   "george.w@university.edu"),
    ("stu-008",   "Hannah Lee",           "student",   "hannah.l@university.edu"),
]

DUMMY_SESSIONS = [
    ("session-001", "CS 101 — Intro to Algorithms", "Big-O Notation",     "prof-001"),
    ("session-002", "CS 201 — Data Structures",     "Binary Search Trees", "prof-001"),
    ("session-003", "MATH 301 — Linear Algebra",    "Eigenvalues",         "prof-002"),
]

# Which students are in which session
DUMMY_MEMBERS = [
    # Session 1: 5 students
    ("session-001", "prof-001"),
    ("session-001", "stu-001"),
    ("session-001", "stu-002"),
    ("session-001", "stu-003"),
    ("session-001", "stu-004"),
    ("session-001", "stu-005"),
    # Session 2: 4 students
    ("session-002", "prof-001"),
    ("session-002", "stu-003"),
    ("session-002", "stu-004"),
    ("session-002", "stu-006"),
    ("session-002", "stu-007"),
    # Session 3: 3 students
    ("session-003", "prof-002"),
    ("session-003", "stu-005"),
    ("session-003", "stu-006"),
    ("session-003", "stu-008"),
]

DUMMY_ESCALATIONS = [
    ("session-001", "stu-002", "Big-O confused",     "Why is O(n log n) faster than O(n²)?"),
    ("session-001", "stu-004", "recursion unclear",   "How does recursion relate to Big-O?"),
    ("session-003", "stu-008", "eigenvalue meaning",  "What does an eigenvalue represent geometrically?"),
]


def seed_db():
    """Insert dummy data if tables are empty."""
    conn = get_conn()
    cursor = conn.cursor()

    # Only seed if users table is empty
    count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        conn.close()
        return

    now = _now_iso()

    # Users
    cursor.executemany(
        "INSERT INTO users (id, name, role, email, created_at) VALUES (?, ?, ?, ?, ?)",
        [(uid, name, role, email, now) for uid, name, role, email in DUMMY_USERS],
    )

    # Sessions
    cursor.executemany(
        "INSERT INTO sessions (id, title, topic, transcript, professor_id, created_at, updated_at) "
        "VALUES (?, ?, ?, '', ?, ?, ?)",
        [(sid, title, topic, pid, now, now) for sid, title, topic, pid in DUMMY_SESSIONS],
    )

    # Members
    cursor.executemany(
        "INSERT INTO session_members (session_id, user_id, joined_at) VALUES (?, ?, ?)",
        [(sid, uid, now) for sid, uid in DUMMY_MEMBERS],
    )

    # Escalations
    cursor.executemany(
        "INSERT INTO escalations (session_id, student_id, tag, query, created_at) VALUES (?, ?, ?, ?, ?)",
        [(sid, stid, tag, q, now) for sid, stid, tag, q in DUMMY_ESCALATIONS],
    )

    conn.commit()
    conn.close()
    print("🌱  Database seeded with dummy data")


# ──────────────────────────────────────────────
# Query helpers
# ──────────────────────────────────────────────

def get_user(user_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_users(role: str = None) -> list[dict]:
    conn = get_conn()
    if role:
        rows = conn.execute("SELECT * FROM users WHERE role = ?", (role,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session(session_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_sessions(professor_id: str = None, active_only: bool = True) -> list[dict]:
    conn = get_conn()
    sql = "SELECT * FROM sessions WHERE 1=1"
    params = []
    if professor_id:
        sql += " AND professor_id = ?"
        params.append(professor_id)
    if active_only:
        sql += " AND is_active = 1"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_members(session_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT u.* FROM users u "
        "JOIN session_members sm ON u.id = sm.user_id "
        "WHERE sm.session_id = ?",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student_sessions(student_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT s.* FROM sessions s "
        "JOIN session_members sm ON s.id = sm.session_id "
        "WHERE sm.user_id = ? AND s.is_active = 1",
        (student_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_session_topic(session_id: str, topic: str):
    conn = get_conn()
    conn.execute(
        "UPDATE sessions SET topic = ?, updated_at = ? WHERE id = ?",
        (topic, _now_iso(), session_id),
    )
    conn.commit()
    conn.close()


def update_session_transcript(session_id: str, transcript: str):
    conn = get_conn()
    conn.execute(
        "UPDATE sessions SET transcript = ?, updated_at = ? WHERE id = ?",
        (transcript, _now_iso(), session_id),
    )
    conn.commit()
    conn.close()


def add_escalation(session_id: str, student_id: str, tag: str, query: str = "") -> dict:
    conn = get_conn()
    now = _now_iso()
    cursor = conn.execute(
        "INSERT INTO escalations (session_id, student_id, tag, query, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (session_id, student_id, tag, query, now),
    )
    esc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": esc_id, "session_id": session_id, "student_id": student_id,
            "tag": tag, "query": query, "created_at": now}


def get_escalations(session_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM escalations WHERE session_id = ? ORDER BY created_at DESC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────
# Auto-init on import
# ──────────────────────────────────────────────
init_db()
seed_db()
