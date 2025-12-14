"""
Mock token data provider for development.

Generates realistic-looking token data without making actual API calls.
Uses deterministic random generation based on address for consistent results.
"""

import hashlib
import random

from bot.core.models import RugpullFlags, SocialInfo, TokenData


class MockTokenDataProvider:
    """
    Mock implementation of TokenDataProvider protocol.

    Generates fake but realistic token data for development and testing.
    The same address always returns the same data (deterministic).

    Usage:
        provider = MockTokenDataProvider()
        data = await provider.get_token_data("So111...")
    """

    # Realistic token name/symbol pairs for mocking
    MOCK_TOKENS = [
        ("Bonk", "BONK"),
        ("Dogwifhat", "WIF"),
        ("Jupiter", "JUP"),
        ("Raydium", "RAY"),
        ("Marinade", "MNDE"),
        ("Orca", "ORCA"),
        ("Pyth", "PYTH"),
        ("Jito", "JTO"),
        ("Tensor", "TNSR"),
        ("Helium", "HNT"),
    ]

    async def get_token_data(self, address: str) -> TokenData:
        """
        Generate mock token data for the given address.

        Uses hash of address as random seed for deterministic results.
        The same address always produces the same data.

        Args:
            address: Solana token address

        Returns:
            TokenData with mock values
        """
        # Create deterministic seed from address
        seed = int(hashlib.md5(address.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)

        # Pick a random token name/symbol
        name, symbol = rng.choice(self.MOCK_TOKENS)

        # Generate realistic metrics
        age_days = rng.randint(1, 365)
        liquidity_usd = rng.uniform(1_000, 500_000)
        holders = rng.randint(10, 50_000)
        top10_percent = rng.uniform(10, 95)
        tx_count = rng.randint(5, 10_000)

        # Generate rugpull flags based on metrics
        rugpull_flags = RugpullFlags(
            new_contract=age_days < 7,
            low_liquidity=liquidity_usd < 20_000,
            centralized_holders=top10_percent > 60,
            developer_wallet_moves=rng.random() < 0.1,  # 10% chance
        )

        # Generate social info
        social = SocialInfo(
            twitter_exists=rng.random() > 0.3,  # 70% have Twitter
            telegram_exists=rng.random() > 0.4,  # 60% have Telegram
            website_valid=rng.random() > 0.5,  # 50% have website
        )

        return TokenData(
            chain="solana",
            address=address,
            name=name,
            symbol=symbol,
            age_days=age_days,
            liquidity_usd=round(liquidity_usd, 2),
            holders=holders,
            top10_holders_percent=round(top10_percent, 2),
            tx_count_24h=tx_count,
            rugpull_flags=rugpull_flags,
            social=social,
        )


class MockTokenDataProviderWithPresets(MockTokenDataProvider):
    """
    Extended mock provider with preset scenarios.

    Allows testing specific risk levels by using known addresses.
    Useful for UI/UX testing.
    """

    # Preset addresses for testing specific scenarios
    PRESETS = {
        # High risk token
        "HighRiskToken11111111111111111111111111111": {
            "age_days": 2,
            "liquidity_usd": 5_000,
            "top10_holders_percent": 85,
        },
        # Medium risk token
        "MediumRiskToken111111111111111111111111111": {
            "age_days": 15,
            "liquidity_usd": 50_000,
            "top10_holders_percent": 45,
        },
        # Low risk token
        "LowRiskToken1111111111111111111111111111111": {
            "age_days": 180,
            "liquidity_usd": 500_000,
            "top10_holders_percent": 25,
        },
    }

    async def get_token_data(self, address: str) -> TokenData:
        """
        Get token data, using presets for known addresses.

        Args:
            address: Solana token address

        Returns:
            TokenData with preset or random values
        """
        # Check if address has a preset
        if address in self.PRESETS:
            preset = self.PRESETS[address]
            return TokenData(
                chain="solana",
                address=address,
                name="TestToken",
                symbol="TEST",
                age_days=preset["age_days"],
                liquidity_usd=preset["liquidity_usd"],
                holders=1000,
                top10_holders_percent=preset["top10_holders_percent"],
                tx_count_24h=100,
                rugpull_flags=RugpullFlags(
                    new_contract=preset["age_days"] < 7,
                    low_liquidity=preset["liquidity_usd"] < 20_000,
                    centralized_holders=preset["top10_holders_percent"] > 60,
                ),
                social=SocialInfo(
                    twitter_exists=True,
                    telegram_exists=True,
                    website_valid=True,
                ),
            )

        # Fall back to random generation
        return await super().get_token_data(address)
