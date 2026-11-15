"""Tests for prompt building."""

import json

from app.llm import build_messages
from app.llm.prompt import SYSTEM_PROMPT

CONTEXT = {"cash": 10000.0, "positions": [], "watchlist": [{"ticker": "AAPL", "price": 190.0}]}


def test_build_messages_order():
    history = [
        {"role": "user", "content": "hi", "actions": None, "created_at": "t1"},
        {"role": "assistant", "content": "hello", "actions": {"trades": []}, "created_at": "t2"},
    ]
    msgs = build_messages(CONTEXT, history, "buy 5 AAPL")
    assert [m["role"] for m in msgs] == ["system", "system", "user", "assistant", "user"]
    assert msgs[0]["content"] == SYSTEM_PROMPT
    assert msgs[-1] == {"role": "user", "content": "buy 5 AAPL"}


def test_context_embedded_as_json():
    msgs = build_messages(CONTEXT, [], "x")
    payload = msgs[1]["content"].split("\n", 1)[1]
    assert json.loads(payload) == CONTEXT


def test_history_strips_extra_fields():
    history = [{"role": "user", "content": "hi", "actions": None, "created_at": "t"}]
    msgs = build_messages(CONTEXT, history, "x")
    assert msgs[2] == {"role": "user", "content": "hi"}


def test_system_prompt_identity():
    assert "FinAlly, an AI trading assistant" in SYSTEM_PROMPT
