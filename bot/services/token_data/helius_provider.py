"""
Helius token data provider.

Fetches on-chain token data from Helius DAS API and RPC.
This is the real implementation used in production.

Responsibilities:
1. Fetch asset metadata via getAsset
2. Fetch largest holders via getTokenLargestAccounts
3. Normalize data into TokenData model
4. Handle errors and timeouts gracefully

NO business logic, NO risk calculation.
"""

import asyncio
import logging

import aiohttp

from bot.core.exceptions import DataFetchError
from bot.core.models import RugpullFlags, SocialInfo, TokenData

logger = logging.getLogger(__name__)

# Helius API endpoint
HELIUS_RPC_URL = "https://mainnet.helius-rpc.com"

# Default timeout (increased for slower API responses)
DEFAULT_TIMEOUT = 10.0


class HeliusTokenDataProvider:
    """
    Real implementation of TokenDataProvider using Helius API.

    Uses:
    - getAsset (DAS API) for token metadata and authorities
    - getTokenLargestAccounts (RPC) for holder concentration

    Timeout: Default 10.0 seconds. Factory configures 1.2s for Telegram UX.
    Retry: 1 time on failure
    """

    def __init__(self, api_key: str, timeout: float = DEFAULT_TIMEOUT):
        """
        Initialize Helius provider.

        Args:
            api_key: Helius API key
            timeout: Request timeout in seconds (default 1.2s)
        """
        self._api_key = api_key
        self._timeout = timeout
        self._base_url = f"{HELIUS_RPC_URL}/?api-key={api_key}"

    async def get_token_data(self, address: str) -> TokenData:
        """
        Fetch token data from Helius.

        Args:
            address: Solana token mint address

        Returns:
            TokenData with all available information

        Raises:
            DataFetchError: If API is unavailable or token not found
        """
        logger.info(f"Fetching token data from Helius: {address[:8]}...")

        try:
            async with aiohttp.ClientSession() as session:
                # Fetch asset metadata and largest accounts in parallel
                asset_task = self._fetch_asset(session, address)
                holders_task = self._fetch_largest_accounts(session, address)

                results = await asyncio.gather(
                    asset_task, holders_task, return_exceptions=True
                )

                asset_result, holders_result = results

                # If ANY result is DataFetchError → API is unavailable, raise it
                for result in results:
                    if isinstance(result, DataFetchError):
                        raise result
                    if isinstance(result, Exception):
                        # Unexpected exception → treat as API error
                        logger.error(f"Unexpected error in API call: {result}")
                        raise DataFetchError(
                            message="Ошибка получения данных.",
                            technical_message=f"Unexpected: {type(result).__name__}: {result}",
                        )

                # Both None = token doesn't exist (API worked but no data)
                if asset_result is None and holders_result is None:
                    raise DataFetchError(
                        message="Токен не найден. Проверьте адрес.",
                        technical_message=f"Token {address} not found in Helius",
                    )

                # At least one succeeded → build TokenData with available data
                return self._build_token_data(address, asset_result, holders_result)

        except DataFetchError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected Helius error: {e}")
            raise DataFetchError(
                message="Не удалось получить данные о токене.",
                technical_message=f"Helius error: {type(e).__name__}: {e}",
            ) from e

    async def _fetch_asset(
        self, session: aiohttp.ClientSession, address: str
    ) -> dict | None:
        """
        Fetch asset metadata via getAsset (DAS API).

        Returns token info including:
        - name, symbol
        - mint_authority, freeze_authority
        - supply, decimals
        - mutable (metadata)

        Raises:
            DataFetchError: On API unavailability (timeout, HTTP 5xx, network error)

        Returns:
            dict: Asset data if found
            None: If token not found (HTTP 4xx or RPC "not found" error)
        """
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "getAsset",
            "params": {"id": address, "options": {"showFungible": True}},
        }

        timeout = aiohttp.ClientTimeout(total=self._timeout)

        try:
            async with session.post(
                self._base_url, json=payload, timeout=timeout
            ) as resp:
                # HTTP 5xx = API unavailable → raise
                if resp.status >= 500:
                    raise DataFetchError(
                        message="Сервис временно недоступен. Попробуйте позже.",
                        technical_message=f"getAsset HTTP {resp.status}",
                    )

                # HTTP 4xx = client error (invalid address, etc) → token not found
                if resp.status != 200:
                    logger.warning(f"getAsset returned {resp.status}")
                    return None

                data = await resp.json()

                if "error" in data:
                    error_msg = str(data.get("error", "")).lower()
                    # RPC "not found" / "invalid" errors → token doesn't exist
                    if "not found" in error_msg or "invalid" in error_msg:
                        logger.info(f"getAsset: token not found ({error_msg})")
                        return None
                    # Other RPC errors → API problem → raise
                    raise DataFetchError(
                        message="Не удалось получить данные о токене.",
                        technical_message=f"getAsset RPC error: {data['error']}",
                    )

                return data.get("result")

        except DataFetchError:
            raise  # Re-raise our errors
        except TimeoutError:
            raise DataFetchError(
                message="Сервис временно недоступен. Попробуйте позже.",
                technical_message="getAsset timeout",
            ) from None
        except aiohttp.ClientError as e:
            raise DataFetchError(
                message="Не удалось получить данные. Проверьте подключение.",
                technical_message=f"getAsset network error: {e}",
            ) from None

    async def _fetch_largest_accounts(
        self, session: aiohttp.ClientSession, address: str
    ) -> list | None:
        """
        Fetch largest token accounts via getTokenLargestAccounts (RPC).

        Returns up to 20 largest holders with their balances.

        Raises:
            DataFetchError: On API unavailability (timeout, HTTP 5xx, network error)

        Returns:
            list: Holder accounts if found
            None: If token not found (HTTP 4xx or RPC "not found" error)
        """
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "getTokenLargestAccounts",
            "params": [address],
        }

        timeout = aiohttp.ClientTimeout(total=self._timeout)

        try:
            async with session.post(
                self._base_url, json=payload, timeout=timeout
            ) as resp:
                # HTTP 5xx = API unavailable → raise
                if resp.status >= 500:
                    raise DataFetchError(
                        message="Сервис временно недоступен. Попробуйте позже.",
                        technical_message=f"getTokenLargestAccounts HTTP {resp.status}",
                    )

                # HTTP 4xx = client error → token not found
                if resp.status != 200:
                    logger.warning(f"getTokenLargestAccounts returned {resp.status}")
                    return None

                data = await resp.json()

                if "error" in data:
                    # Any RPC error for holders = data unavailable, not API failure
                    # Examples: "not found", "invalid", "too many accounts", etc.
                    # Holders data is optional - we can proceed without it
                    error_msg = data.get("error", {})
                    if isinstance(error_msg, dict):
                        error_msg = error_msg.get("message", str(error_msg))
                    logger.info(
                        f"getTokenLargestAccounts: holders unavailable ({error_msg})"
                    )
                    return None

                return data.get("result", {}).get("value")

        except DataFetchError:
            raise  # Re-raise HTTP 5xx errors only
        except TimeoutError:
            # Timeout for holders = data unavailable, not critical
            logger.info("getTokenLargestAccounts: timeout, proceeding without holders")
            return None
        except aiohttp.ClientError as e:
            # Network error for holders = data unavailable, not critical
            logger.info(f"getTokenLargestAccounts: network error ({e}), proceeding without holders")
            return None

    def _build_token_data(
        self,
        address: str,
        asset_data: dict | None,
        holders_data: list | None,
    ) -> TokenData:
        """
        Build TokenData from API responses.

        Handles missing data gracefully with safe defaults.
        """
        # Extract basic info from asset
        name = None
        symbol = None
        mint_authority_exists = None
        freeze_authority_exists = None
        metadata_mutable = None
        supply = 0
        decimals = 0

        if asset_data:
            # Content (name, symbol)
            content = asset_data.get("content", {})
            metadata = content.get("metadata", {})
            name = metadata.get("name")
            symbol = metadata.get("symbol")

            # Token info (authorities, supply)
            token_info = asset_data.get("token_info", {})
            mint_authority_exists = token_info.get("mint_authority") is not None
            freeze_authority_exists = token_info.get("freeze_authority") is not None
            supply = int(token_info.get("supply", 0))
            decimals = int(token_info.get("decimals", 0))

            # Mutable flag
            metadata_mutable = asset_data.get("mutable")

        # Calculate holder concentration
        top1_percent = None
        top2_percent = None
        top5_percent = None
        top10_percent = 0.0

        if holders_data and supply > 0:
            concentrations = self._calculate_holder_concentration(
                holders_data, supply, decimals
            )
            top1_percent = concentrations.get("top1")
            top2_percent = concentrations.get("top2")
            top5_percent = concentrations.get("top5")
            top10_percent = concentrations.get("top10", 0.0)

        # Age and liquidity: None = data unavailable
        # Helius DAS API doesn't provide creation time or liquidity
        # Risk engine will handle None values gracefully
        age_days = None
        liquidity_usd = None

        # Build rugpull flags based on available data
        # Use None-safe checks for optional values
        rugpull_flags = RugpullFlags(
            new_contract=False,  # Unknown age, don't assume
            low_liquidity=False,  # Unknown liquidity, don't assume
            centralized_holders=top10_percent > 60 if top10_percent else False,
            developer_wallet_moves=False,  # Would need transaction history
        )

        return TokenData(
            chain="solana",
            address=address,
            name=name,
            symbol=symbol or "UNKNOWN",
            age_days=age_days,  # None = unknown
            liquidity_usd=liquidity_usd,  # None = unknown
            holders=len(holders_data) if holders_data else 0,
            top10_holders_percent=round(top10_percent, 2),
            tx_count_24h=0,  # Would need transaction history
            mint_authority_exists=mint_authority_exists,
            freeze_authority_exists=freeze_authority_exists,
            metadata_mutable=metadata_mutable,
            top1_holder_percent=round(top1_percent, 2) if top1_percent else None,
            top2_holder_percent=round(top2_percent, 2) if top2_percent else None,
            top5_holders_percent=round(top5_percent, 2) if top5_percent else None,
            rugpull_flags=rugpull_flags,
            social=SocialInfo(),  # Helius doesn't provide social info
        )

    def _calculate_holder_concentration(
        self,
        holders: list,
        total_supply: int,
        decimals: int,
    ) -> dict:
        """
        Calculate holder concentration percentages.

        Args:
            holders: List of holder accounts from getTokenLargestAccounts
            total_supply: Total token supply (raw units)
            decimals: Token decimals

        Returns:
            Dict with top1, top5, top10 percentages
        """
        if not holders or total_supply <= 0:
            return {}

        # Normalize supply to UI units
        ui_supply = total_supply / (10**decimals) if decimals > 0 else total_supply

        if ui_supply <= 0:
            return {}

        # Sort by amount descending (should already be sorted, but ensure)
        sorted_holders = sorted(
            holders,
            key=lambda h: float(h.get("uiAmount", 0) or 0),
            reverse=True,
        )

        # Calculate concentrations
        result = {}

        if len(sorted_holders) >= 1:
            top1_amount = float(sorted_holders[0].get("uiAmount", 0) or 0)
            result["top1"] = (top1_amount / ui_supply) * 100

        if len(sorted_holders) >= 2:
            top2_amount = float(sorted_holders[1].get("uiAmount", 0) or 0)
            result["top2"] = (top2_amount / ui_supply) * 100

        if len(sorted_holders) >= 5:
            top5_amount = sum(
                float(h.get("uiAmount", 0) or 0) for h in sorted_holders[:5]
            )
            result["top5"] = (top5_amount / ui_supply) * 100

        if len(sorted_holders) >= 10:
            top10_amount = sum(
                float(h.get("uiAmount", 0) or 0) for h in sorted_holders[:10]
            )
            result["top10"] = (top10_amount / ui_supply) * 100
        elif sorted_holders:
            # If less than 10 holders, use all of them
            total_amount = sum(float(h.get("uiAmount", 0) or 0) for h in sorted_holders)
            result["top10"] = (total_amount / ui_supply) * 100

        return result
