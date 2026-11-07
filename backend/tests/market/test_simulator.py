"""Tests for GBMSimulator."""

import math

import numpy as np
import pytest

from app.market.seed_prices import SEED_PRICES
from app.market.simulator import GBMSimulator


class TestGBMSimulator:
    """Unit tests for the GBM price simulator."""

    def test_step_returns_all_tickers(self):
        """Test that step() returns prices for all tickers."""
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        result = sim.step()
        assert set(result.keys()) == {"AAPL", "GOOGL"}

    def test_prices_are_positive(self):
        """GBM prices can never go negative (exp() is always positive)."""
        sim = GBMSimulator(tickers=["AAPL"])
        for _ in range(10_000):
            prices = sim.step()
            assert prices["AAPL"] > 0

    def test_initial_prices_match_seeds(self):
        """Test that initial prices match seed prices."""
        sim = GBMSimulator(tickers=["AAPL"])
        # Before any step, price should be the seed price
        assert sim.get_price("AAPL") == SEED_PRICES["AAPL"]

    def test_add_ticker(self):
        """Test adding a ticker dynamically."""
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("TSLA")
        result = sim.step()
        assert "TSLA" in result

    def test_remove_ticker(self):
        """Test removing a ticker."""
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        sim.remove_ticker("GOOGL")
        result = sim.step()
        assert "GOOGL" not in result
        assert "AAPL" in result

    def test_add_duplicate_is_noop(self):
        """Test that adding a duplicate ticker is a no-op."""
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("AAPL")
        assert len(sim._tickers) == 1

    def test_remove_nonexistent_is_noop(self):
        """Test that removing a non-existent ticker is a no-op."""
        sim = GBMSimulator(tickers=["AAPL"])
        sim.remove_ticker("NOPE")  # Should not raise

    def test_unknown_ticker_seed_in_range(self):
        """Unknown tickers get a seed price between $50 and $300."""
        sim = GBMSimulator(tickers=["ZZZZ"])
        price = sim.get_price("ZZZZ")
        assert price is not None
        assert 50.0 <= price <= 300.0

    def test_empty_step(self):
        """Test stepping with no tickers."""
        sim = GBMSimulator(tickers=[])
        result = sim.step()
        assert result == {}

    def test_prices_change_over_time(self):
        """After many steps, prices should have drifted from their seeds."""
        sim = GBMSimulator(tickers=["AAPL"])
        initial_price = sim.get_price("AAPL")

        for _ in range(1000):
            sim.step()

        final_price = sim.get_price("AAPL")
        # Price should have changed (extremely unlikely to be exactly the seed)
        assert final_price != initial_price

    def test_cholesky_rebuilds_on_add(self):
        """Test that Cholesky matrix is rebuilt when tickers are added."""
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim._cholesky is None  # Only 1 ticker, no correlation matrix
        sim.add_ticker("GOOGL")
        assert sim._cholesky is not None  # Now 2 tickers, matrix exists

    def test_cholesky_none_with_one_ticker(self):
        """Test that Cholesky is None with only one ticker."""
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim._cholesky is None

    def test_get_price_returns_none_for_unknown(self):
        """Test that get_price returns None for unknown ticker."""
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim.get_price("UNKNOWN") is None

    def test_pairwise_correlation_tech_stocks(self):
        """Test that tech stocks have high correlation."""
        corr = GBMSimulator._pairwise_correlation("AAPL", "GOOGL")
        assert corr == 0.6

    def test_pairwise_correlation_finance_stocks(self):
        """Test that finance stocks have moderate correlation."""
        corr = GBMSimulator._pairwise_correlation("JPM", "V")
        assert corr == 0.5

    def test_pairwise_correlation_tsla(self):
        """Test that TSLA has lower correlation with everything."""
        corr = GBMSimulator._pairwise_correlation("TSLA", "AAPL")
        assert corr == 0.3
        corr = GBMSimulator._pairwise_correlation("TSLA", "JPM")
        assert corr == 0.3

    def test_pairwise_correlation_cross_sector(self):
        """Test cross-sector correlation."""
        corr = GBMSimulator._pairwise_correlation("AAPL", "JPM")
        assert corr == 0.3

    def test_default_dt_is_reasonable(self):
        """Test that default dt is a reasonable small value."""
        assert 0 < GBMSimulator.DEFAULT_DT < 0.0001

    def test_prices_rounded_to_two_decimals(self):
        """step() returns prices rounded to cents."""
        sim = GBMSimulator(tickers=["AAPL", "TSLA"])
        for _ in range(100):
            for price in sim.step().values():
                assert round(price, 2) == price


def test_seed_price_tracked():
    """Seed price stays fixed while the live price moves, and is dropped on remove."""
    sim = GBMSimulator(["AAPL"], event_probability=0.0)
    for _ in range(100):
        sim.step()
    assert sim.get_seed_price("AAPL") == 190.00
    assert sim.get_price("AAPL") != 190.00
    sim.remove_ticker("AAPL")
    assert sim.get_seed_price("AAPL") is None


def test_unknown_ticker_seed_is_deterministic():
    """An unknown ticker gets the same seed price in every simulator (e.g. after restart)."""
    assert GBMSimulator(["ZZZZ"]).get_seed_price("ZZZZ") == GBMSimulator(["ZZZZ"]).get_seed_price(
        "ZZZZ"
    )
    assert GBMSimulator(["ZZZZ"]).get_seed_price("ZZZZ") != GBMSimulator(["YYYY"]).get_seed_price(
        "YYYY"
    )


def _log_returns(tickers: list[str], steps: int) -> np.ndarray:
    """Per-step log returns (steps x tickers) from a seeded, event-free simulator."""
    np.random.seed(42)
    sim = GBMSimulator(tickers, event_probability=0.0)
    prices = [[sim._prices[t] for t in tickers]]
    for _ in range(steps):
        sim.step()
        prices.append([sim._prices[t] for t in tickers])
    return np.diff(np.log(np.array(prices)), axis=0)


def test_gbm_volatility_matches_sigma():
    """Per-tick log-return std is sigma * sqrt(dt) (AAPL sigma=0.22, TSLA sigma=0.50)."""
    returns = _log_returns(["AAPL", "TSLA"], 20_000)
    dt = GBMSimulator.DEFAULT_DT
    for i, sigma in enumerate([0.22, 0.50]):
        assert returns[:, i].std() == pytest.approx(sigma * math.sqrt(dt), rel=0.03)


def test_gbm_correlations_match_sector_groups():
    """Realised correlations match the configured tech / finance / TSLA structure."""
    tickers = ["AAPL", "GOOGL", "JPM", "V", "TSLA"]
    corr = np.corrcoef(_log_returns(tickers, 20_000).T)
    assert corr[0, 1] == pytest.approx(0.6, abs=0.03)  # tech-tech
    assert corr[2, 3] == pytest.approx(0.5, abs=0.03)  # finance-finance
    assert corr[0, 2] == pytest.approx(0.3, abs=0.03)  # cross-sector
    assert corr[4, 0] == pytest.approx(0.3, abs=0.03)  # TSLA


def test_cholesky_handles_many_tickers():
    """The correlation matrix stays positive-definite with 60 mixed tickers."""
    tickers = list(SEED_PRICES) + [f"X{i}" for i in range(50)]
    sim = GBMSimulator(tickers)
    assert sim._cholesky.shape == (60, 60)


def test_duplicate_initial_tickers_tracked_once():
    assert GBMSimulator(["AAPL", "AAPL"]).get_tickers() == ["AAPL"]
