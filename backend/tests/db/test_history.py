"""Tests for portfolio snapshots and chat messages."""

import pytest

from app.db import add_chat_message, get_chat_messages, get_snapshots, record_snapshot


def test_snapshots_oldest_first():
    for v in (1.0, 2.0, 3.0):
        record_snapshot(v)
    snaps = get_snapshots()
    assert [s["total_value"] for s in snaps] == [1.0, 2.0, 3.0]
    assert set(snaps[0]) == {"total_value", "recorded_at"}


def test_snapshots_limit_keeps_latest():
    for v in range(5):
        record_snapshot(float(v))
    assert [s["total_value"] for s in get_snapshots(limit=2)] == [3.0, 4.0]


def test_chat_roundtrip_with_actions():
    add_chat_message("user", "buy 5 AAPL")
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5, "status": "executed"}]}
    returned = add_chat_message("assistant", "Buying 5 AAPL.", actions)
    assert returned["actions"] == actions
    msgs = get_chat_messages()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["actions"] is None
    assert msgs[1]["actions"] == actions


def test_chat_limit_keeps_latest_oldest_first():
    for i in range(5):
        add_chat_message("user", f"m{i}")
    assert [m["content"] for m in get_chat_messages(limit=2)] == ["m3", "m4"]


def test_chat_rejects_bad_role():
    with pytest.raises(Exception):
        add_chat_message("system", "nope")
