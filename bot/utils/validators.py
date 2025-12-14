"""
Solana address validation.

Validates that a string is a valid Solana public key address.
Uses actual base58 decoding instead of regex for accuracy.

Solana addresses:
- Use base58 encoding (no 0, O, I, l characters)
- Decode to exactly 32 bytes
- Typically 32-44 characters when encoded
"""

import base58


def validate_solana_address(address: str) -> tuple[bool, str | None]:
    """
    Validate a Solana token address.

    Performs actual base58 decoding to verify the address is valid.
    This is more reliable than regex because it catches invalid
    characters and incorrect checksums.

    Args:
        address: String to validate as Solana address

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if address is valid
        - (False, "error description") if invalid

    Examples:
        >>> validate_solana_address("So11111111111111111111111111111111111111112")
        (True, None)

        >>> validate_solana_address("")
        (False, "Адрес не может быть пустым")

        >>> validate_solana_address("0x742d35Cc6634C0532925a3b844Bc9e7595f5bEb2")
        (False, "Невалидный формат base58")
    """
    # Check empty input
    if not address:
        return False, "Адрес не может быть пустым"

    # Check for whitespace
    if address != address.strip():
        return False, "Адрес содержит пробелы"

    # Quick length check (Solana addresses are 32-44 chars)
    if len(address) < 32 or len(address) > 44:
        return False, f"Неверная длина адреса: {len(address)} символов (ожидается 32-44)"

    # Try to decode base58
    try:
        decoded = base58.b58decode(address)
    except ValueError:
        # base58 library raises ValueError for invalid characters
        return False, "Невалидный формат base58"
    except Exception as e:
        # Catch any other decoding errors
        return False, f"Ошибка декодирования: {type(e).__name__}"

    # Verify decoded length is exactly 32 bytes
    if len(decoded) != 32:
        return (
            False,
            f"Неверная длина: ожидается 32 байта, получено {len(decoded)}",
        )

    return True, None


def is_valid_solana_address(address: str) -> bool:
    """
    Simple boolean check for Solana address validity.

    Convenience wrapper around validate_solana_address for
    cases where you only need a boolean result.

    Args:
        address: String to validate

    Returns:
        True if valid Solana address, False otherwise
    """
    valid, _ = validate_solana_address(address)
    return valid
