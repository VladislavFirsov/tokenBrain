"""
Tests for Solana address validation.

Tests cover:
- Valid addresses (real tokens)
- Invalid format (too short, too long)
- Invalid characters (Ethereum, special chars)
- Edge cases (empty, whitespace)
"""

import pytest

from bot.utils.validators import is_valid_solana_address, validate_solana_address


class TestValidateSolanaAddress:
    """Tests for validate_solana_address function."""

    def test_valid_usdc_address(self, valid_solana_address: str) -> None:
        """USDC token address should be valid."""
        is_valid, error = validate_solana_address(valid_solana_address)
        assert is_valid is True
        assert error is None

    def test_valid_wrapped_sol_address(self, another_valid_address: str) -> None:
        """Wrapped SOL address should be valid."""
        is_valid, error = validate_solana_address(another_valid_address)
        assert is_valid is True
        assert error is None

    def test_empty_address(self) -> None:
        """Empty string should be invalid."""
        is_valid, error = validate_solana_address("")
        assert is_valid is False
        assert "пустым" in error.lower()

    def test_whitespace_only(self) -> None:
        """Whitespace-only string should be invalid."""
        is_valid, error = validate_solana_address("   ")
        assert is_valid is False

    def test_address_with_spaces(self, valid_solana_address: str) -> None:
        """Address with leading/trailing spaces should be invalid."""
        is_valid, error = validate_solana_address(f" {valid_solana_address} ")
        assert is_valid is False
        assert "пробелы" in error.lower()

    def test_too_short_address(self) -> None:
        """Address shorter than 32 chars should be invalid."""
        is_valid, error = validate_solana_address("abc123")
        assert is_valid is False
        assert "длина" in error.lower()

    def test_too_long_address(self) -> None:
        """Address longer than 44 chars should be invalid."""
        is_valid, error = validate_solana_address("a" * 50)
        assert is_valid is False
        assert "длина" in error.lower()

    def test_ethereum_address(self) -> None:
        """Ethereum address should be invalid (wrong format)."""
        eth_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f5bEb2"
        is_valid, error = validate_solana_address(eth_address)
        assert is_valid is False

    def test_invalid_base58_characters(self) -> None:
        """Address with invalid base58 chars (0, O, I, l) should be invalid."""
        # These characters are not in base58 alphabet
        invalid_address = "0OIl" + "1" * 40  # 0, O, I, l are invalid
        is_valid, error = validate_solana_address(invalid_address)
        assert is_valid is False
        assert "base58" in error.lower()

    def test_special_characters(self) -> None:
        """Address with special characters should be invalid."""
        is_valid, error = validate_solana_address(
            "So11111111111111111111111111111111111111112!"
        )
        assert is_valid is False

    @pytest.mark.parametrize(
        "address",
        [
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "So11111111111111111111111111111111111111112",  # Wrapped SOL
            "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",  # mSOL
            "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",  # Jupiter
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # Bonk
        ],
    )
    def test_real_token_addresses(self, address: str) -> None:
        """Real Solana token addresses should be valid."""
        is_valid, error = validate_solana_address(address)
        assert is_valid is True, f"Address {address} should be valid: {error}"


class TestIsValidSolanaAddress:
    """Tests for is_valid_solana_address convenience function."""

    def test_returns_true_for_valid(self, valid_solana_address: str) -> None:
        """Should return True for valid address."""
        assert is_valid_solana_address(valid_solana_address) is True

    def test_returns_false_for_invalid(self) -> None:
        """Should return False for invalid address."""
        assert is_valid_solana_address("invalid") is False

    def test_returns_false_for_empty(self) -> None:
        """Should return False for empty string."""
        assert is_valid_solana_address("") is False
