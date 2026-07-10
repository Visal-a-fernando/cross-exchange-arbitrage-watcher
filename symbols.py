"""
utils/symbols.py — Symbol normaliser.

Binance Spot uses 'BTC/U' and 'ETH/U' during the April–July 2026
"United Stables (U)" promotion (0.00% maker/taker fees).
Bybit uses the standard 'BTC/USDT' / 'ETH/USDT' convention.

normalize_symbol() converts any exchange-native symbol to a
canonical (base, quote_unified) tuple for internal comparison.
"""

from __future__ import annotations

# Maps (exchange_id, raw_symbol) → (base, quote_unified)
# "U" on Binance is treated as equivalent to "USDT" internally.
_SYMBOL_MAP: dict[tuple[str, str], tuple[str, str]] = {
    # Binance Spot — United Stables promo pairs
    ("binance", "BTC/U"):    ("BTC", "USDT"),
    ("binance", "ETH/U"):    ("ETH", "USDT"),
    # Binance standard USDT pairs (fallback / futures)
    ("binance", "BTC/USDT"): ("BTC", "USDT"),
    ("binance", "ETH/USDT"): ("ETH", "USDT"),
    ("binance", "LRC/USDT"): ("LRC", "USDT"),
    ("binance", "BERA/USDT"):("BERA", "USDT"),
    # Bybit pairs
    ("bybit",   "BTC/USDT"): ("BTC", "USDT"),
    ("bybit",   "ETH/USDT"): ("ETH", "USDT"),
    ("bybit",   "LRC/USDT"): ("LRC", "USDT"),
    ("bybit",   "BERA/USDT"):("BERA", "USDT"),
}

# Reverse map: (exchange_id, unified_base) → exchange-native symbol
_NATIVE_MAP: dict[tuple[str, str], str] = {
    ("binance", "BTC"):  "BTC/U",       # Use 'U' pair for zero-fee promo
    ("binance", "ETH"):  "ETH/U",
    ("binance", "LRC"):  "LRC/USDT",
    ("binance", "BERA"): "BERA/USDT",
    ("bybit",   "BTC"):  "BTC/USDT",
    ("bybit",   "ETH"):  "ETH/USDT",
    ("bybit",   "LRC"):  "LRC/USDT",
    ("bybit",   "BERA"): "BERA/USDT",
}


def normalize_symbol(exchange_id: str, raw_symbol: str) -> tuple[str, str]:
    """
    Convert an exchange-native symbol to a unified (base, quote) tuple.

    Args:
        exchange_id: 'binance' | 'bybit' (lower-case)
        raw_symbol:  e.g. 'BTC/U', 'ETH/USDT'

    Returns:
        (base, quote_unified) e.g. ('BTC', 'USDT')

    Raises:
        KeyError: if the symbol is not registered in the map.
    """
    key = (exchange_id.lower(), raw_symbol.upper())
    if key in _SYMBOL_MAP:
        return _SYMBOL_MAP[key]
    # Generic fallback: split on '/' and normalise 'U' → 'USDT'
    parts = raw_symbol.upper().split("/")
    if len(parts) == 2:
        base, quote = parts
        if quote == "U":
            quote = "USDT"
        return base, quote
    raise KeyError(f"Unknown symbol '{raw_symbol}' for exchange '{exchange_id}'")


def to_native_symbol(exchange_id: str, base: str) -> str:
    """
    Return the exchange-native symbol string for a given base asset.

    Args:
        exchange_id: 'binance' | 'bybit'
        base:        e.g. 'BTC'

    Returns:
        Native symbol string, e.g. 'BTC/U' (Binance) or 'BTC/USDT' (Bybit)
    """
    key = (exchange_id.lower(), base.upper())
    if key in _NATIVE_MAP:
        return _NATIVE_MAP[key]
    # Fallback
    return f"{base.upper()}/USDT"


def unified_id(base: str, quote_unified: str = "USDT") -> str:
    """Return canonical internal identifier, e.g. 'BTC-USD'."""
    return f"{base}-USD"
