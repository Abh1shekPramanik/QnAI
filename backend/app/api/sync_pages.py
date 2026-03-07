"""
QnAI — Shared Session State Backend (Issue #3)
Flask + Flask-SocketIO server that keeps teacher-set topic and transcript
synchronised across all connected teacher / student clients in real time.

Now backed by SQLite (db.py) to support multiple professors, students,
and concurrent sessions.

Socket events are scoped to a session via SocketIO rooms.
Clients join a room by emitting  join_session { session_id, user_id }
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room

import db

# ──────────────────────────────────────────────
# App & extensions
# ──────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "qnai-dev-secret")

CORS(app, resources={r"/*": {"origins": "*"}})

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=False,
    engineio_logger=False,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_snapshot(session_id: str) -> dict | None:
    """Build a full snapshot for a session from the DB."""
    s = db.get_session(session_id)
    if not s:
        return None
    members = db.get_session_members(session_id)
    escalations = db.get_escalations(session_id)
    return {
        "session_id": s["id"],
        "title": s["title"],
        "topic": s["topic"],
        "transcript": s["transcript"],
        "professor_id": s["professor_id"],
        "is_active": s["is_active"],
        "members": members,
        "escalations": escalations,
        "updated_at": s["updated_at"],
    }


# ──────────────────────────────────────────────
# REST endpoints
# ──────────────────────────────────────────────

@app.route("/api/users", methods=["GET"])
def api_list_users():
    """List all users, optionally filtered by ?role=professor|student."""
    role = request.args.get("role")
    return jsonify(db.list_users(role))


@app.route("/api/users/<user_id>", methods=["GET"])
def api_get_user(user_id):
    user = db.get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)


@app.route("/api/sessions", methods=["GET"])
def api_list_sessions():
    """List sessions. ?professor_id=... to filter by professor."""
    professor_id = request.args.get("professor_id")
    return jsonify(db.list_sessions(professor_id))


@app.route("/api/sessions/<session_id>", methods=["GET"])
def api_get_session(session_id):
    snap = _session_snapshot(session_id)
    if not snap:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(snap)


@app.route("/api/sessions/<session_id>/members", methods=["GET"])
def api_session_members(session_id):
    return jsonify(db.get_session_members(session_id))


@app.route("/api/students/<student_id>/sessions", methods=["GET"])
def api_student_sessions(student_id):
    return jsonify(db.get_student_sessions(student_id))


@app.route("/api/sessions/<session_id>/topic", methods=["POST"])
def api_set_topic(session_id):
    data = request.get_json(force=True)
    topic = data.get("topic", "")
    db.update_session_topic(session_id, topic)
    socketio.emit("topic_updated", {"topic": topic}, room=session_id)
    socketio.emit("session_state", _session_snapshot(session_id), room=session_id)
    return jsonify({"ok": True, "topic": topic})


@app.route("/api/sessions/<session_id>/transcript", methods=["POST"])
def api_set_transcript(session_id):
    data = request.get_json(force=True)
    transcript = data.get("transcript", "")
    db.update_session_transcript(session_id, transcript)
    socketio.emit("transcript_updated", {"transcript": transcript}, room=session_id)
    socketio.emit("session_state", _session_snapshot(session_id), room=session_id)
    return jsonify({"ok": True})


@app.route("/api/sessions/<session_id>/escalation", methods=["POST"])
def api_add_escalation(session_id):
    data = request.get_json(force=True)
    tag = data.get("tag", "")
    student_id = data.get("student_id", "anonymous")
    query = data.get("query", "")
    entry = db.add_escalation(session_id, student_id, tag, query)
    socketio.emit("escalation_added", entry, room=session_id)
    socketio.emit("session_state", _session_snapshot(session_id), room=session_id)
    return jsonify({"ok": True, "escalation": entry})


@app.route("/api/sessions/<session_id>/escalations", methods=["GET"])
def api_get_escalations(session_id):
    return jsonify(db.get_escalations(session_id))


# ──────────────────────────────────────────────
# Backward-compat: old single-session endpoints
# (redirect to session-001 so existing frontend works)
# ──────────────────────────────────────────────

@app.route("/api/state", methods=["GET"])
def api_state_compat():
    snap = _session_snapshot("session-001")
    if not snap:
        return jsonify({"topic": "", "transcript": "", "escalations": [], "updated_at": _now_iso()})
    return jsonify({
        "topic": snap["topic"],
        "transcript": snap["transcript"],
        "escalations": snap["escalations"],
        "updated_at": snap["updated_at"],
    })


@app.route("/api/topic", methods=["POST"])
def api_topic_compat():
    data = request.get_json(force=True)
    topic = data.get("topic", "")
    db.update_session_topic("session-001", topic)
    socketio.emit("topic_updated", {"topic": topic}, room="session-001")
    socketio.emit("session_state", _session_snapshot("session-001"), room="session-001")
    socketio.emit("topic_updated", {"topic": topic})
    return jsonify({"ok": True, "topic": topic})


@app.route("/api/transcript", methods=["POST"])
def api_transcript_compat():
    data = request.get_json(force=True)
    transcript = data.get("transcript", "")
    db.update_session_transcript("session-001", transcript)
    socketio.emit("transcript_updated", {"transcript": transcript}, room="session-001")
    socketio.emit("session_state", _session_snapshot("session-001"), room="session-001")
    socketio.emit("transcript_updated", {"transcript": transcript})
    return jsonify({"ok": True})


@app.route("/api/escalation", methods=["POST"])
def api_escalation_compat():
    data = request.get_json(force=True)
    tag = data.get("tag", "")
    entry = db.add_escalation("session-001", "anonymous", tag)
    socketio.emit("escalation_added", entry, room="session-001")
    socketio.emit("escalation_added", entry)
    return jsonify({"ok": True})


# ──────────────────────────────────────────────
# WebSocket events
# ──────────────────────────────────────────────

@socketio.on("connect")
def handle_connect():
    """Send a welcome; client should then emit join_session."""
    print(f"[ws] client connected  – sid {request.sid}")
    snap = _session_snapshot("session-001")
    if snap:
        emit("session_state", {
            "topic": snap["topic"],
            "transcript": snap["transcript"],
            "escalations": snap["escalations"],
            "updated_at": snap["updated_at"],
        })


@socketio.on("disconnect")
def handle_disconnect():
    print(f"[ws] client disconnected – sid {request.sid}")


@socketio.on("join_session")
def handle_join_session(data):
    """Client joins a session room. { session_id, user_id }"""
    session_id = data.get("session_id", "")
    user_id = data.get("user_id", "")
    join_room(session_id)
    snap = _session_snapshot(session_id)
    if snap:
        emit("session_state", snap)
    print(f"[ws] {user_id} joined room {session_id}")


@socketio.on("leave_session")
def handle_leave_session(data):
    session_id = data.get("session_id", "")
    leave_room(session_id)
    print(f"[ws] client left room {session_id}")


@socketio.on("request_state")
def handle_request_state(data=None):
    session_id = (data or {}).get("session_id", "session-001")
    snap = _session_snapshot(session_id)
    if snap:
        emit("session_state", snap)


@socketio.on("set_topic")
def handle_set_topic(data):
    session_id = data.get("session_id", "session-001")
    topic = data.get("topic", "")
    db.update_session_topic(session_id, topic)
    socketio.emit("topic_updated", {"topic": topic}, room=session_id)
    socketio.emit("session_state", _session_snapshot(session_id), room=session_id)
    if session_id == "session-001":
        socketio.emit("topic_updated", {"topic": topic})
    print(f"[ws] topic → {topic!r}  (session {session_id})")


@socketio.on("set_transcript")
def handle_set_transcript(data):
    session_id = data.get("session_id", "session-001")
    transcript = data.get("transcript", "")
    db.update_session_transcript(session_id, transcript)
    socketio.emit("transcript_updated", {"transcript": transcript}, room=session_id)
    socketio.emit("session_state", _session_snapshot(session_id), room=session_id)
    if session_id == "session-001":
        socketio.emit("transcript_updated", {"transcript": transcript})


@socketio.on("add_escalation")
def handle_add_escalation(data):
    session_id = data.get("session_id", "session-001")
    student_id = data.get("student_id", "anonymous")
    tag = data.get("tag", "")
    query = data.get("query", "")
    entry = db.add_escalation(session_id, student_id, tag, query)
    socketio.emit("escalation_added", entry, room=session_id)
    socketio.emit("session_state", _session_snapshot(session_id), room=session_id)
    if session_id == "session-001":
        socketio.emit("escalation_added", entry)
    print(f"[ws] escalation → {tag!r}  (session {session_id})")


# ──────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"🚀  QnAI session server starting on :{port}")
    print(f"📦  Database at {db.DB_PATH}")
    print(f"👥  Users: {len(db.list_users())}")
    print(f"📚  Sessions: {len(db.list_sessions())}")
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
