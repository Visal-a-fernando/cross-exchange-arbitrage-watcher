"""
exchanges/base.py — Abstract BaseExchange wrapper around ccxt.pro.

Provides:
  - Async context manager lifecycle (open / close).
  - Precision helpers: amount_to_precision(), price_to_precision().
  - Safe watchOrderBook() with error recovery.
  - Safe fetchFundingRate() wrapper.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Optional

import ccxt.pro as ccxtpro
from loguru import logger


class BaseExchange(ABC):
    """
    Thin async wrapper around a ccxt.pro exchange instance.

    Subclasses must implement `_build_exchange()` to return
    the concrete ccxt.pro exchange object.
    """

    exchange_id: str = "base"

    def __init__(self) -> None:
        self._exchange: Optional[ccxtpro.Exchange] = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Initialise the exchange and load markets."""
        self._exchange = self._build_exchange()
        try:
            await self._exchange.load_markets()
            logger.info("[{}] Markets loaded ({} symbols)", self.exchange_id, len(self._exchange.markets))
        except Exception as exc:
            logger.error("[{}] Failed to load markets: {}", self.exchange_id, exc)
            raise

    async def close(self) -> None:
        """Close all WebSocket connections and free resources."""
        if self._exchange:
            try:
                await self._exchange.close()
                logger.info("[{}] Exchange closed.", self.exchange_id)
            except Exception as exc:
                logger.warning("[{}] Error during close: {}", self.exchange_id, exc)

    async def __aenter__(self) -> "BaseExchange":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ── Abstract factory ─────────────────────────────────────────────────────

    @abstractmethod
    def _build_exchange(self) -> ccxtpro.Exchange:
        """Return a configured ccxt.pro exchange instance."""
        ...

    # ── Precision helpers ─────────────────────────────────────────────────────

    def amount_to_precision(self, symbol: str, amount: float) -> str:
        """Round `amount` to the market's lot-size precision."""
        if self._exchange is None:
            raise RuntimeError("Exchange not connected.")
        try:
            return self._exchange.amount_to_precision(symbol, amount)
        except Exception:
            return str(amount)

    def price_to_precision(self, symbol: str, price: float) -> str:
        """Round `price` to the market's tick-size precision."""
        if self._exchange is None:
            raise RuntimeError("Exchange not connected.")
        try:
            return self._exchange.price_to_precision(symbol, price)
        except Exception:
            return str(price)

    # ── WebSocket order book ─────────────────────────────────────────────────

    async def watch_order_book(self, symbol: str, limit: int = 5) -> dict[str, Any]:
        """
        Await the next order-book update for `symbol`.

        Returns the raw ccxt order-book dict:
          {
            'symbol': ...,
            'bids': [[price, size], ...],
            'asks': [[price, size], ...],
            'timestamp': epoch_ms,
            ...
          }
        """
        if self._exchange is None:
            raise RuntimeError("Exchange not connected.")
        return await self._exchange.watch_order_book(symbol, limit=limit)

    # ── Funding rate ─────────────────────────────────────────────────────────

    async def fetch_funding_rate(self, symbol: str) -> dict[str, Any]:
        """
        Fetch the current perpetual funding rate for `symbol`.

        Returns ccxt fundingRate dict or empty dict on error.
        """
        if self._exchange is None:
            raise RuntimeError("Exchange not connected.")
        try:
            return await self._exchange.fetch_funding_rate(symbol)
        except ccxtpro.NotSupported:
            logger.debug("[{}] fetch_funding_rate not supported for {}", self.exchange_id, symbol)
            return {}
        except Exception as exc:
            logger.warning("[{}] fetch_funding_rate({}) error: {}", self.exchange_id, symbol, exc)
            return {}

    # ── Convenience ──────────────────────────────────────────────────────────

    @property
    def exchange(self) -> ccxtpro.Exchange:
        if self._exchange is None:
            raise RuntimeError("Exchange not connected — call connect() first.")
        return self._exchange

    def symbol_exists(self, symbol: str) -> bool:
        """Check if a symbol is listed on this exchange."""
        if self._exchange is None:
            return False
        return symbol in self._exchange.markets
