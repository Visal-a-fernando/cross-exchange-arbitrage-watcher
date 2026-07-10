"""
exchanges/binance.py — Binance Spot + USDM Futures connections via ccxt.pro.

Two separate instances are used:
  - BinanceSpot   → Spot market (BTC/U, ETH/U zero-fee promo pairs)
  - BinanceFutures → USDM Perpetual (for funding rates on LRC, BERA)

April–July 2026 "United Stables (U)" promotion:
  BTC/U and ETH/U pairs have 0.00% maker/taker fee on Binance Spot.
  Use to_native_symbol('binance', base) to get the correct pair string.
"""

from __future__ import annotations

import ccxt.pro as ccxtpro
from exchanges.base import BaseExchange
from config import BINANCE_API_KEY, BINANCE_API_SECRET


class BinanceSpot(BaseExchange):
    exchange_id = "binance"

    def _build_exchange(self) -> ccxtpro.Exchange:
        return ccxtpro.binance(
            {
                "apiKey": BINANCE_API_KEY or "",
                "secret": BINANCE_API_SECRET or "",
                # Enable public WebSocket without authentication
                "options": {
                    "defaultType": "spot",
                    # Prefer the United Stables endpoint when available
                    "adjustForTimeDifference": True,
                },
                # Disable signed requests if no keys provided
                "enableRateLimit": True,
            }
        )


class BinanceFutures(BaseExchange):
    """Binance USDM Futures — used only for funding rate polling."""

    exchange_id = "binance_futures"

    def _build_exchange(self) -> ccxtpro.Exchange:
        return ccxtpro.binance(
            {
                "apiKey": BINANCE_API_KEY or "",
                "secret": BINANCE_API_SECRET or "",
                "options": {
                    "defaultType": "future",
                    "adjustForTimeDifference": True,
                },
                "enableRateLimit": True,
            }
        )
