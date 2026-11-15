"""Tests for the LiteLLM client with `completion` patched (no network)."""

from types import SimpleNamespace

import pytest

from app.llm import LLMResponse, get_llm_response
from app.llm.client import EXTRA_BODY, FALLBACK_MESSAGE, MODEL


def _fake_completion(content, calls=None):
    """Return a fake completion() yielding `content` and recording kwargs."""

    def fake(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        msg = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    return fake


@pytest.fixture(autouse=True)
def real_mode(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "false")


def test_valid_full_response(monkeypatch):
    content = (
        '{"message": "Done", "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],'
        ' "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]}'
    )
    calls = []
    monkeypatch.setattr("app.llm.client.completion", _fake_completion(content, calls))
    r = get_llm_response({"cash": 1}, [], "buy 10 AAPL and watch PYPL")
    assert r.message == "Done"
    assert r.trades[0].quantity == 10
    assert r.watchlist_changes[0].action == "add"
    kw = calls[0]
    assert kw["model"] == MODEL
    assert kw["extra_body"] == EXTRA_BODY
    assert kw["response_format"] is LLMResponse
    assert kw["reasoning_effort"] == "low"
    assert kw["messages"][-1]["content"] == "buy 10 AAPL and watch PYPL"


def test_message_only(monkeypatch):
    monkeypatch.setattr("app.llm.client.completion", _fake_completion('{"message": "Hi"}'))
    assert get_llm_response({}, [], "hi") == LLMResponse(message="Hi")


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "",
        None,
        '{"trades": []}',
        '{"message": "x", "trades": [{"ticker": "AAPL", "side": "hold", "quantity": 1}]}',
    ],
)
def test_malformed_falls_back(monkeypatch, content):
    monkeypatch.setattr("app.llm.client.completion", _fake_completion(content))
    assert get_llm_response({}, [], "hi") == LLMResponse(message=FALLBACK_MESSAGE)


def test_completion_error_falls_back(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("app.llm.client.completion", boom)
    assert get_llm_response({}, [], "hi").message == FALLBACK_MESSAGE
