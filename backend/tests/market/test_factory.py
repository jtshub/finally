"""Tests for market data source factory."""

import os
from unittest.mock import patch

from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.massive_client import MassiveDataSource
from app.market.simulator import SimulatorDataSource


class TestFactory:
    """Tests for create_market_data_source factory."""

    def test_creates_simulator_when_no_api_key(self):
        """Test that simulator is created when MASSIVE_API_KEY is not set."""
        cache = PriceCache()

        with patch.dict(os.environ, {}, clear=True):
            source = create_market_data_source(cache)

        assert isinstance(source, SimulatorDataSource)

    def test_creates_simulator_when_api_key_empty(self):
        """Test that simulator is created when MASSIVE_API_KEY is empty."""
        cache = PriceCache()

        with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}, clear=True):
            source = create_market_data_source(cache)

        assert isinstance(source, SimulatorDataSource)

    def test_creates_simulator_when_api_key_whitespace(self):
        """Test that simulator is created when MASSIVE_API_KEY is whitespace."""
        cache = PriceCache()

        with patch.dict(os.environ, {"MASSIVE_API_KEY": "   "}, clear=True):
            source = create_market_data_source(cache)

        assert isinstance(source, SimulatorDataSource)

    def test_creates_massive_when_api_key_set(self):
        """Test that Massive client is created when MASSIVE_API_KEY is set."""
        cache = PriceCache()

        with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key"}, clear=True):
            source = create_market_data_source(cache)

        assert isinstance(source, MassiveDataSource)

    def test_massive_receives_api_key(self):
        """Test that Massive client receives the API key."""
        cache = PriceCache()

        with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key-123"}, clear=True):
            source = create_market_data_source(cache)

        assert isinstance(source, MassiveDataSource)
        assert source._client.API_KEY == "test-key-123"

    def test_simulator_receives_cache(self):
        """Test that simulator receives the cache reference."""
        cache = PriceCache()

        with patch.dict(os.environ, {}, clear=True):
            source = create_market_data_source(cache)

        assert isinstance(source, SimulatorDataSource)
        assert source._cache is cache

    def test_massive_receives_cache(self):
        """Test that Massive client receives the cache reference."""
        cache = PriceCache()

        with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key"}, clear=True):
            source = create_market_data_source(cache)

        assert isinstance(source, MassiveDataSource)
        assert source._cache is cache

    def test_massive_default_poll_interval(self):
        """Massive polls every 15s by default."""
        with patch.dict(os.environ, {"MASSIVE_API_KEY": "k"}, clear=True):
            source = create_market_data_source(PriceCache())
        assert source._interval == 15.0

    def test_massive_poll_interval_from_env(self):
        """MASSIVE_POLL_INTERVAL overrides the poll interval."""
        env = {"MASSIVE_API_KEY": "k", "MASSIVE_POLL_INTERVAL": "2.5"}
        with patch.dict(os.environ, env, clear=True):
            source = create_market_data_source(PriceCache())
        assert source._interval == 2.5

    def test_empty_poll_interval_uses_default(self):
        """MASSIVE_POLL_INTERVAL= (present but empty) falls back to 15s."""
        env = {"MASSIVE_API_KEY": "k", "MASSIVE_POLL_INTERVAL": ""}
        with patch.dict(os.environ, env, clear=True):
            source = create_market_data_source(PriceCache())
        assert source._interval == 15.0

    def test_poll_interval_has_floor(self):
        """Intervals below 1s are raised to 1s so the API is not hammered."""
        env = {"MASSIVE_API_KEY": "k", "MASSIVE_POLL_INTERVAL": "0"}
        with patch.dict(os.environ, env, clear=True):
            source = create_market_data_source(PriceCache())
        assert source._interval == 1.0
