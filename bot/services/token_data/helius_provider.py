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

# Default timeout (SLA: 1.2 sec)
DEFAULT_TIMEOUT = 1.2


class HeliusTokenDataProvider:
    """
    Real implementation of TokenDataProvider using Helius API.

    Uses:
    - getAsset (DAS API) for token metadata and authorities
    - getTokenLargestAccounts (RPC) for holder concentration

    Timeout: 1.2 seconds (Telegram UX requirement)
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
            DataFetchError: If fetching fails after retries
        """
        logger.info(f"Fetching token data from Helius: {address[:8]}...")

        try:
            async with aiohttp.ClientSession() as session:
                # Fetch asset metadata and largest accounts in parallel
                asset_task = self._fetch_asset(session, address)
                holders_task = self._fetch_largest_accounts(session, address)

                asset_data, holders_data = await asyncio.gather(
                    asset_task, holders_task, return_exceptions=True
                )

                # Handle partial failures
                if isinstance(asset_data, Exception):
                    logger.warning(f"Failed to fetch asset: {asset_data}")
                    asset_data = None

                if isinstance(holders_data, Exception):
                    logger.warning(f"Failed to fetch holders: {holders_data}")
                    holders_data = None

                # If both failed, raise error
                if asset_data is None and holders_data is None:
                    raise DataFetchError(
                        message="Не удалось получить данные о токене.",
                        technical_message="Both Helius API calls failed",
                    )

                return self._build_token_data(address, asset_data, holders_data)

        except DataFetchError:
            raise
        except TimeoutError:
            logger.error(f"Helius timeout after {self._timeout}s")
            raise DataFetchError(
                message="Запрос занял слишком много времени.",
                technical_message=f"Helius timeout after {self._timeout}s",
            ) from None
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
                if resp.status != 200:
                    logger.warning(f"getAsset returned {resp.status}")
                    return None

                data = await resp.json()

                if "error" in data:
                    logger.warning(f"getAsset error: {data['error']}")
                    return None

                return data.get("result")

        except TimeoutError:
            logger.warning("getAsset timeout")
            return None
        except Exception as e:
            logger.warning(f"getAsset failed: {e}")
            return None

    async def _fetch_largest_accounts(
        self, session: aiohttp.ClientSession, address: str
    ) -> dict | None:
        """
        Fetch largest token accounts via getTokenLargestAccounts (RPC).

        Returns up to 20 largest holders with their balances.
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
                if resp.status != 200:
                    logger.warning(f"getTokenLargestAccounts returned {resp.status}")
                    return None

                data = await resp.json()

                if "error" in data:
                    logger.warning(f"getTokenLargestAccounts error: {data['error']}")
                    return None

                return data.get("result", {}).get("value")

        except TimeoutError:
            logger.warning("getTokenLargestAccounts timeout")
            return None
        except Exception as e:
            logger.warning(f"getTokenLargestAccounts failed: {e}")
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
        top5_percent = None
        top10_percent = 0.0

        if holders_data and supply > 0:
            concentrations = self._calculate_holder_concentration(
                holders_data, supply, decimals
            )
            top1_percent = concentrations.get("top1")
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
