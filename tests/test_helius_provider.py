"""
Tests for HeliusTokenDataProvider.

Tests cover:
- Successful API responses
- Partial data handling
- Error handling and timeouts
- Holder concentration calculation
"""

import pytest
from aioresponses import aioresponses

from bot.core.exceptions import DataFetchError
from bot.services.token_data.helius_provider import (
    HELIUS_RPC_URL,
    HeliusTokenDataProvider,
)


@pytest.fixture
def helius_provider() -> HeliusTokenDataProvider:
    """HeliusTokenDataProvider with test API key."""
    return HeliusTokenDataProvider(api_key="test-api-key", timeout=1.0)


@pytest.fixture
def mock_asset_response() -> dict:
    """Mock getAsset response."""
    return {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "content": {
                "metadata": {
                    "name": "Test Token",
                    "symbol": "TEST",
                }
            },
            "token_info": {
                "mint_authority": None,
                "freeze_authority": None,
                "supply": 1000000000000,  # 1M with 6 decimals
                "decimals": 6,
            },
            "mutable": False,
        },
    }


@pytest.fixture
def mock_asset_with_authorities_response() -> dict:
    """Mock getAsset response with authorities present."""
    return {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "content": {
                "metadata": {
                    "name": "Risky Token",
                    "symbol": "RISK",
                }
            },
            "token_info": {
                "mint_authority": "SomeAuthority111111111111111111111111111",
                "freeze_authority": "SomeAuthority111111111111111111111111111",
                "supply": 1000000000000,
                "decimals": 6,
            },
            "mutable": True,
        },
    }


@pytest.fixture
def mock_holders_response() -> dict:
    """Mock getTokenLargestAccounts response."""
    return {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "value": [
                {"address": "holder1", "amount": "500000000000", "uiAmount": 500000.0},
                {"address": "holder2", "amount": "200000000000", "uiAmount": 200000.0},
                {"address": "holder3", "amount": "100000000000", "uiAmount": 100000.0},
                {"address": "holder4", "amount": "50000000000", "uiAmount": 50000.0},
                {"address": "holder5", "amount": "50000000000", "uiAmount": 50000.0},
                {"address": "holder6", "amount": "25000000000", "uiAmount": 25000.0},
                {"address": "holder7", "amount": "25000000000", "uiAmount": 25000.0},
                {"address": "holder8", "amount": "20000000000", "uiAmount": 20000.0},
                {"address": "holder9", "amount": "15000000000", "uiAmount": 15000.0},
                {"address": "holder10", "amount": "15000000000", "uiAmount": 15000.0},
            ]
        },
    }


class TestHeliusProviderSuccess:
    """Tests for successful API responses."""

    @pytest.mark.asyncio
    async def test_get_token_data_success(
        self,
        helius_provider: HeliusTokenDataProvider,
        mock_asset_response: dict,
        mock_holders_response: dict,
    ) -> None:
        """Should fetch and parse token data correctly."""
        with aioresponses() as m:
            url = f"{HELIUS_RPC_URL}/?api-key=test-api-key"
            m.post(url, payload=mock_asset_response)
            m.post(url, payload=mock_holders_response)

            result = await helius_provider.get_token_data(
                "TestToken11111111111111111111111111111111"
            )

            assert result.name == "Test Token"
            assert result.symbol == "TEST"
            assert result.mint_authority_exists is False
            assert result.freeze_authority_exists is False
            assert result.metadata_mutable is False

    @pytest.mark.asyncio
    async def test_detects_authorities(
        self,
        helius_provider: HeliusTokenDataProvider,
        mock_asset_with_authorities_response: dict,
        mock_holders_response: dict,
    ) -> None:
        """Should detect when authorities are present."""
        with aioresponses() as m:
            url = f"{HELIUS_RPC_URL}/?api-key=test-api-key"
            m.post(url, payload=mock_asset_with_authorities_response)
            m.post(url, payload=mock_holders_response)

            result = await helius_provider.get_token_data(
                "RiskyToken1111111111111111111111111111111"
            )

            assert result.mint_authority_exists is True
            assert result.freeze_authority_exists is True
            assert result.metadata_mutable is True


class TestHeliusProviderHolderConcentration:
    """Tests for holder concentration calculation."""

    @pytest.mark.asyncio
    async def test_calculates_holder_percentages(
        self,
        helius_provider: HeliusTokenDataProvider,
        mock_asset_response: dict,
        mock_holders_response: dict,
    ) -> None:
        """Should calculate top1, top5, top10 percentages correctly."""
        with aioresponses() as m:
            url = f"{HELIUS_RPC_URL}/?api-key=test-api-key"
            m.post(url, payload=mock_asset_response)
            m.post(url, payload=mock_holders_response)

            result = await helius_provider.get_token_data(
                "TestToken11111111111111111111111111111111"
            )

            # Total supply: 1M, top1: 500k = 50%
            assert result.top1_holder_percent is not None
            assert result.top1_holder_percent == pytest.approx(50.0, rel=0.1)

            # Top 5: 500k + 200k + 100k + 50k + 50k = 900k = 90%
            assert result.top5_holders_percent is not None
            assert result.top5_holders_percent == pytest.approx(90.0, rel=0.1)

            # Top 10: all = 1M = 100%
            assert result.top10_holders_percent == pytest.approx(100.0, rel=0.1)


class TestHeliusProviderErrors:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_timeout_raises_data_fetch_error(
        self,
        helius_provider: HeliusTokenDataProvider,
    ) -> None:
        """Timeout should raise DataFetchError."""

        with aioresponses() as m:
            url = f"{HELIUS_RPC_URL}/?api-key=test-api-key"
            m.post(url, exception=TimeoutError())
            m.post(url, exception=TimeoutError())

            with pytest.raises(DataFetchError) as exc_info:
                await helius_provider.get_token_data(
                    "TestToken11111111111111111111111111111111"
                )

            assert "временно недоступен" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_handles_api_error(
        self,
        helius_provider: HeliusTokenDataProvider,
    ) -> None:
        """Should raise DataFetchError on API error."""
        with aioresponses() as m:
            url = f"{HELIUS_RPC_URL}/?api-key=test-api-key"
            m.post(url, status=500)
            m.post(url, status=500)

            with pytest.raises(DataFetchError):
                await helius_provider.get_token_data(
                    "TestToken11111111111111111111111111111111"
                )

    @pytest.mark.asyncio
    async def test_both_not_found_raises_token_not_found(
        self,
        helius_provider: HeliusTokenDataProvider,
    ) -> None:
        """Both APIs returning 'not found' should raise DataFetchError."""
        not_found_response = {
            "jsonrpc": "2.0",
            "id": "1",
            "error": {"message": "Account not found"},
        }

        with aioresponses() as m:
            url = f"{HELIUS_RPC_URL}/?api-key=test-api-key"
            m.post(url, payload=not_found_response)
            m.post(url, payload=not_found_response)

            with pytest.raises(DataFetchError) as exc_info:
                await helius_provider.get_token_data(
                    "NonExistent111111111111111111111111111111"
                )

            assert "токен не найден" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_http_500_raises_error(
        self,
        helius_provider: HeliusTokenDataProvider,
        mock_asset_response: dict,
    ) -> None:
        """HTTP 500 from any call should raise DataFetchError."""
        with aioresponses() as m:
            url = f"{HELIUS_RPC_URL}/?api-key=test-api-key"
            m.post(url, payload=mock_asset_response)
            m.post(url, status=500)  # Holders API returns 500

            # Should raise error (API unavailable)
            with pytest.raises(DataFetchError) as exc_info:
                await helius_provider.get_token_data(
                    "TestToken11111111111111111111111111111111"
                )

            assert "недоступен" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_handles_partial_data_not_found(
        self,
        helius_provider: HeliusTokenDataProvider,
        mock_asset_response: dict,
    ) -> None:
        """Asset success + holders 'not found' should return TokenData."""
        not_found_response = {
            "jsonrpc": "2.0",
            "id": "1",
            "error": {"message": "Invalid token account"},
        }

        with aioresponses() as m:
            url = f"{HELIUS_RPC_URL}/?api-key=test-api-key"
            m.post(url, payload=mock_asset_response)
            m.post(url, payload=not_found_response)  # Holders not found

            # Should still return data from asset API
            result = await helius_provider.get_token_data(
                "TestToken11111111111111111111111111111111"
            )

            assert result.name == "Test Token"
            assert result.top1_holder_percent is None  # No holder data

    @pytest.mark.asyncio
    async def test_handles_json_rpc_error(
        self,
        helius_provider: HeliusTokenDataProvider,
    ) -> None:
        """Should handle JSON-RPC error responses."""
        error_response = {
            "jsonrpc": "2.0",
            "id": "1",
            "error": {"code": -32000, "message": "Asset not found"},
        }

        with aioresponses() as m:
            url = f"{HELIUS_RPC_URL}/?api-key=test-api-key"
            m.post(url, payload=error_response)
            m.post(url, payload=error_response)

            with pytest.raises(DataFetchError):
                await helius_provider.get_token_data(
                    "NonexistentToken111111111111111111111111"
                )
