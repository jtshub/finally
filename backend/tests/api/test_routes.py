"""Route tests against the contract shapes."""


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_fresh_portfolio(client):
    data = client.get("/api/portfolio").json()
    assert data["cash"] == 10000.0
    assert data["total_value"] == 10000.0
    assert data["positions"] == []


def test_watchlist_default_has_prices(client):
    rows = client.get("/api/watchlist").json()
    assert [r["ticker"] for r in rows][:3] == ["AAPL", "GOOGL", "MSFT"]
    assert len(rows) == 10
    assert rows[0]["price"] > 0
    assert set(rows[0]) == {
        "ticker",
        "price",
        "previous_price",
        "change_percent",
        "day_change_percent",
        "direction",
    }


def test_buy_then_sell(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "aapl", "quantity": 2, "side": "buy"})
    assert r.status_code == 200
    body = r.json()
    assert body["trade"]["ticker"] == "AAPL"
    pos = body["portfolio"]["positions"][0]
    assert pos["quantity"] == 2
    assert body["portfolio"]["cash"] < 10000.0

    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 2, "side": "sell"})
    assert r.status_code == 200
    assert r.json()["portfolio"]["positions"] == []


def test_trade_records_snapshot(client):
    client.post("/api/portfolio/trade", json={"ticker": "MSFT", "quantity": 1, "side": "buy"})
    history = client.get("/api/portfolio/history").json()
    assert len(history) == 1
    assert set(history[0]) == {"total_value", "recorded_at"}


def test_trade_errors_are_400(client):
    cases = [
        {"ticker": "AAPL", "quantity": 1000, "side": "buy"},
        {"ticker": "AAPL", "quantity": 1, "side": "sell"},
        {"ticker": "AAPL", "quantity": 0, "side": "buy"},
        {"ticker": "AAPL", "quantity": 1, "side": "hold"},
        {"ticker": "ZZZZ", "quantity": 1, "side": "buy"},
    ]
    for body in cases:
        r = client.post("/api/portfolio/trade", json=body)
        assert r.status_code == 400, body
        assert r.json()["detail"]


def test_watchlist_add_remove(client):
    r = client.post("/api/watchlist", json={"ticker": "pypl"})
    assert r.status_code == 201
    assert r.json() == {"ticker": "PYPL"}
    row = client.get("/api/watchlist").json()[-1]
    assert row["ticker"] == "PYPL" and row["price"] > 0
    assert client.post("/api/watchlist", json={"ticker": "PYPL"}).status_code == 400
    assert client.delete("/api/watchlist/PYPL").json() == {"ticker": "PYPL"}
    assert client.delete("/api/watchlist/PYPL").status_code == 404
    assert client.app.state.cache.get("PYPL") is None


def test_watchlist_invalid_ticker(client):
    assert client.post("/api/watchlist", json={"ticker": "bad ticker!"}).status_code == 400


def test_remove_held_ticker_keeps_streaming(client):
    client.post("/api/portfolio/trade", json={"ticker": "NVDA", "quantity": 1, "side": "buy"})
    assert client.delete("/api/watchlist/NVDA").status_code == 200
    assert client.app.state.cache.get("NVDA") is not None
    assert client.get("/api/portfolio").json()["positions"][0]["ticker"] == "NVDA"


def test_chat_mock_buy(client):
    r = client.post("/api/chat", json={"message": "buy 3 AAPL"})
    data = r.json()
    assert data["message"] == "Buying 3 AAPL."
    trade = data["trades"][0]
    assert trade["status"] == "executed" and trade["price"] > 0 and trade["error"] is None
    assert client.get("/api/portfolio").json()["positions"][0]["quantity"] == 3


def test_chat_failed_trade(client):
    data = client.post("/api/chat", json={"message": "sell 5 TSLA"}).json()
    assert data["trades"][0]["status"] == "failed"
    assert data["trades"][0]["error"]


def test_chat_watchlist_and_history(client):
    data = client.post("/api/chat", json={"message": "watch PYPL"}).json()
    assert data["watchlist_changes"] == [
        {"ticker": "PYPL", "action": "add", "status": "executed", "error": None}
    ]
    history = client.get("/api/chat/history").json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[0]["actions"] is None
    assert history[1]["actions"]["watchlist_changes"][0]["ticker"] == "PYPL"


def test_chat_plain_message(client):
    data = client.post("/api/chat", json={"message": "hello"}).json()
    assert data == {
        "message": "Mock response: I can help with your portfolio.",
        "trades": [],
        "watchlist_changes": [],
    }


def test_chat_empty_message(client):
    assert client.post("/api/chat", json={"message": "  "}).status_code == 400
