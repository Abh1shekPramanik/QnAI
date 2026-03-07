import sqlite3
import os
from datetime import datetime, timezone

# DB_PATH relative to the root 'backend' folder
DB_PATH = os.path.join(os.getcwd(), "qnai.db")

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def get_conn() -> sqlite3.Connection:
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
    bot_id      TEXT UNIQUE,
    zoom_url    TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcripts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    speaker     TEXT NOT NULL,
    text        TEXT NOT NULL,
    is_final    INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
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
    category    TEXT NOT NULL DEFAULT '',
    query       TEXT NOT NULL DEFAULT '',
    addressed   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_context (
    session_id      TEXT PRIMARY KEY REFERENCES sessions(id),
    current_subtopic TEXT NOT NULL DEFAULT 'unknown',
    key_terms       TEXT NOT NULL DEFAULT '[]',
    examples        TEXT NOT NULL DEFAULT '[]',
    raw_buffer      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_queries (
    query_id    TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    student_id  TEXT NOT NULL DEFAULT 'anonymous',
    query       TEXT NOT NULL,
    ai_answer   TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
"""

def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    
    # Check for missing columns (in case DB already exists)
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN bot_id TEXT UNIQUE")
        conn.execute("ALTER TABLE sessions ADD COLUMN zoom_url TEXT")
    except sqlite3.OperationalError:
        pass # Already exists

    try:
        conn.execute("ALTER TABLE escalations ADD COLUMN category TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE escalations ADD COLUMN addressed INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

# ──────────────────────────────────────────────
# Seed dummy data
# ──────────────────────────────────────────────

DUMMY_USERS = [
    ("prof-001",  "Professor",      "professor", "example1@university.edu"),
    ("stu-001",   "Alice Student",  "student",   "alice@university.edu"),
]

def seed_db():
    conn = get_conn()
    cursor = conn.cursor()
    count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        conn.close()
        return

    now = _now_iso()
    cursor.executemany(
        "INSERT INTO users (id, name, role, email, created_at) VALUES (?, ?, ?, ?, ?)",
        [(uid, name, role, email, now) for uid, name, role, email in DUMMY_USERS],
    )
    cursor.execute(
        "INSERT INTO sessions (id, title, topic, transcript, professor_id, created_at, updated_at) "
        "VALUES (?, ?, ?, '', ?, ?, ?)",
        ("session-001", "Main Lecture", "General", "prof-001", now, now)
    )
    conn.commit()
    conn.close()

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
    sql = "SELECT * FROM users"
    params = []
    if role:
        sql += " WHERE role = ?"
        params.append(role)
    rows = conn.execute(sql, params).fetchall()
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

def update_session_topic(session_id: str, topic: str):
    conn = get_conn()
    conn.execute(
        "UPDATE sessions SET topic = ?, updated_at = ? WHERE id = ?",
        (topic, _now_iso(), session_id),
    )
    conn.commit()
    conn.close()

def update_session_bot_id(session_id: str, bot_id: str, zoom_url: str):
    conn = get_conn()
    conn.execute(
        "UPDATE sessions SET bot_id = ?, zoom_url = ?, updated_at = ? WHERE id = ?",
        (bot_id, zoom_url, _now_iso(), session_id),
    )
    conn.commit()
    conn.close()

def get_session_by_bot_id(bot_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE bot_id = ?", (bot_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def save_transcript(session_id: str, speaker: str, text: str, is_final: bool = True):
    conn = get_conn()
    conn.execute(
        "INSERT INTO transcripts (session_id, speaker, text, is_final, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (session_id, speaker, text, 1 if is_final else 0, _now_iso()),
    )
    conn.commit()
    conn.close()

def get_transcripts(session_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM transcripts WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_session_members(session_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT u.* FROM users u JOIN session_members sm ON u.id = sm.user_id WHERE sm.session_id = ?",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_escalation(session_id: str, student_id: str, tag: str, query: str = "") -> dict:
    conn = get_conn()
    now = _now_iso()
    # Check if student exists, if not, create mock
    if not get_user(student_id):
        conn.execute("INSERT OR IGNORE INTO users (id, name, role, created_at) VALUES (?, ?, ?, ?)", 
                    (student_id, student_id, 'student', now))
    
    cursor = conn.execute(
        "INSERT INTO escalations (session_id, student_id, tag, query, created_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, student_id, tag, query, now),
    )
    esc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": esc_id, "session_id": session_id, "student_id": student_id, "tag": tag, "query": query, "created_at": now}

def get_escalations(session_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM escalations WHERE session_id = ? ORDER BY created_at DESC", (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ──────────────────────────────────────────────
# Session context helpers
# ──────────────────────────────────────────────

def save_context(session_id: str, context: dict, raw_buffer: str = ""):
    import json
    conn = get_conn()
    now = _now_iso()
    conn.execute(
        "INSERT INTO session_context (session_id, current_subtopic, key_terms, examples, raw_buffer, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(session_id) DO UPDATE SET "
        "current_subtopic=excluded.current_subtopic, key_terms=excluded.key_terms, "
        "examples=excluded.examples, raw_buffer=excluded.raw_buffer, updated_at=excluded.updated_at",
        (session_id,
         context.get("current_subtopic", "unknown"),
         json.dumps(context.get("key_terms", [])),
         json.dumps(context.get("examples", [])),
         raw_buffer,
         now),
    )
    conn.commit()
    conn.close()

def get_context(session_id: str) -> dict | None:
    import json
    conn = get_conn()
    row = conn.execute("SELECT * FROM session_context WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["key_terms"] = json.loads(d["key_terms"])
    d["examples"] = json.loads(d["examples"])
    return d

# ──────────────────────────────────────────────
# Pending query helpers (Layer 1 → Layer 2)
# ──────────────────────────────────────────────

def save_pending_query(query_id: str, session_id: str, student_id: str, query: str, ai_answer: str) -> dict:
    conn = get_conn()
    now = _now_iso()
    conn.execute(
        "INSERT INTO pending_queries (query_id, session_id, student_id, query, ai_answer, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (query_id, session_id, student_id, query, ai_answer, now),
    )
    conn.commit()
    conn.close()
    return {"query_id": query_id, "session_id": session_id, "student_id": student_id,
            "query": query, "ai_answer": ai_answer, "created_at": now}

def get_pending_query(query_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM pending_queries WHERE query_id = ?", (query_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

# ──────────────────────────────────────────────
# Escalation helpers (with category + addressed)
# ──────────────────────────────────────────────

def add_escalation_with_category(session_id: str, student_id: str, tag: str, category: str, query: str = "") -> dict:
    conn = get_conn()
    now = _now_iso()
    if not get_user(student_id):
        conn.execute("INSERT OR IGNORE INTO users (id, name, role, created_at) VALUES (?, ?, ?, ?)",
                    (student_id, student_id, 'student', now))
    cursor = conn.execute(
        "INSERT INTO escalations (session_id, student_id, tag, category, query, addressed, created_at) "
        "VALUES (?, ?, ?, ?, ?, 0, ?)",
        (session_id, student_id, tag, category, query, now),
    )
    esc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": esc_id, "session_id": session_id, "student_id": student_id,
            "tag": tag, "category": category, "query": query, "addressed": False, "created_at": now}

def get_escalations_grouped(session_id: str) -> list[dict]:
    """Returns escalations grouped by category for the teacher dashboard."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT category, COUNT(*) as count, "
        "GROUP_CONCAT(id) as tag_ids, GROUP_CONCAT(tag, '||') as tags "
        "FROM escalations WHERE session_id = ? AND addressed = 0 "
        "GROUP BY category ORDER BY count DESC",
        (session_id,),
    ).fetchall()
    conn.close()

    groups = []
    for r in rows:
        d = dict(r)
        d["tag_ids"] = d["tag_ids"].split(",") if d["tag_ids"] else []
        d["tags"] = d["tags"].split("||") if d["tags"] else []
        groups.append(d)
    return groups

def mark_escalations_addressed(tag_ids: list[int]):
    conn = get_conn()
    placeholders = ",".join("?" * len(tag_ids))
    conn.execute(f"UPDATE escalations SET addressed = 1 WHERE id IN ({placeholders})", tag_ids)
    conn.commit()
    conn.close()

def get_existing_categories(session_id: str) -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT category FROM escalations WHERE session_id = ? AND category != ''",
        (session_id,),
    ).fetchall()
    conn.close()
    return [r["category"] for r in rows]

# Auto-init
init_db()
seed_db()
