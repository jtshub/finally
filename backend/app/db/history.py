"""Portfolio value snapshots and chat messages."""

import json

from app.db.connection import DEFAULT_USER, new_id, now_iso, transaction


def record_snapshot(total_value: float, user_id: str = DEFAULT_USER) -> None:
    """Store the current total portfolio value."""
    with transaction() as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) VALUES (?, ?, ?, ?)",
            (new_id(), user_id, total_value, now_iso()),
        )


def get_snapshots(user_id: str = DEFAULT_USER, limit: int = 1000) -> list[dict]:
    """Return the latest `limit` snapshots as {total_value, recorded_at}, oldest first."""
    with transaction() as conn:
        rows = conn.execute(
            "SELECT total_value, recorded_at FROM portfolio_snapshots WHERE user_id = ? "
            "ORDER BY recorded_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def add_chat_message(
    role: str, content: str, actions: dict | list | None = None, user_id: str = DEFAULT_USER
) -> dict:
    """Store a chat message (actions JSON-encoded) and return it."""
    msg = {"id": new_id(), "role": role, "content": content, "actions": actions, "created_at": now_iso()}
    encoded = None if actions is None else json.dumps(actions)
    with transaction() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (msg["id"], user_id, role, content, encoded, msg["created_at"]),
        )
    return msg


def get_chat_messages(user_id: str = DEFAULT_USER, limit: int = 20) -> list[dict]:
    """Return the latest `limit` messages, oldest first, with actions decoded."""
    with transaction() as conn:
        rows = conn.execute(
            "SELECT id, role, content, actions, created_at FROM chat_messages WHERE user_id = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [{**dict(r), "actions": json.loads(r["actions"]) if r["actions"] else None} for r in reversed(rows)]
