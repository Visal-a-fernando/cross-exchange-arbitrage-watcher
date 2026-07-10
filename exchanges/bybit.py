"""
exchanges/bybit.py — Bybit Spot + USDT Perpetual connections via ccxt.pro.

Two separate instances are used:
  - BybitSpot       → Spot market (BTC/USDT, ETH/USDT)
  - BybitPerpetual  → USDT Perpetual (for funding rates on LRC, BERA)

Bybit taker fee: 0.06%.
"""

from __future__ import annotations

import ccxt.pro as ccxtpro
from exchanges.base import BaseExchange
from config import BYBIT_API_KEY, BYBIT_API_SECRET


class BybitSpot(BaseExchange):
    exchange_id = "bybit"

    def _build_exchange(self) -> ccxtpro.Exchange:
        return ccxtpro.bybit(
            {
                "apiKey": BYBIT_API_KEY or "",
                "secret": BYBIT_API_SECRET or "",
                "options": {
                    "defaultType": "spot",
                    "adjustForTimeDifference": True,
                },
                "enableRateLimit": True,
            }
        )


class BybitPerpetual(BaseExchange):
    """Bybit USDT Perpetual — used only for funding rate polling."""

    exchange_id = "bybit_perp"

    def _build_exchange(self) -> ccxtpro.Exchange:
        return ccxtpro.bybit(
            {
                "apiKey": BYBIT_API_KEY or "",
                "secret": BYBIT_API_SECRET or "",
                "options": {
                    "defaultType": "linear",   # USDT perpetual
                    "adjustForTimeDifference": True,
                },
                "enableRateLimit": True,
            }
        )
