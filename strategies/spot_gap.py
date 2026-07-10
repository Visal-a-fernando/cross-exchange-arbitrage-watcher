"""
strategies/spot_gap.py — Spot Gap Monitor (Section 5A).

Algorithm:
  1. asyncio.gather on watchOrderBook for Binance (limit=5) and
     Bybit (limit=50) simultaneously.
  2. Extract best ask (Binance) and best bid (Bybit).
  3. Crossed-book check: skip if binance_ask >= bybit_bid.
  4. Liquidity check: aggregate notional across top 5 levels within
     0.1% of best price; skip if min side < $1,000.
  5. Calculate net spread after fee budget (0.08%).
  6. Time-sync check: compare exchange timestamps; skip if diff
     exceeds DEBUG_MODE threshold (1000ms) or production (200ms).
  7. Alert if net_spread > 0.15%.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from config import (
    DEBUG_MODE,
    FEE_BUDGET,
    LEG_SIZE_USD,
    MIN_LEG_NOTIONAL,
    PROFIT_THRESHOLD,
    SPOT_PAIRS,
    TIME_SYNC_THRESHOLD_MS,
)
from exchanges.binance import BinanceSpot
from exchanges.bybit import BybitSpot
from utils.notifier import alert_latency_spike, alert_spot_gap
from utils.state import BotState
from utils.time_sync import check_time_sync, ts_diff_ms

_time_sync_checked = False   # Perform startup drift check on first tick


def _extract_top(book: dict[str, Any], side: str) -> tuple[float, float]:
    """
    Return (best_price, size) for 'bids' or 'asks'.
    Raises IndexError if the book is empty.
    """
    levels = book.get(side, [])
    if not levels:
        raise IndexError(f"Empty {side} side in order book")
    price, size = levels[0][0], levels[0][1]
    return float(price), float(size)


def _aggregate_notional(
    book: dict[str, Any],
    side: str,
    max_levels: int = 5,
    price_tolerance: float = 0.001,
) -> tuple[float, float]:
    """
    Sum notional (price × size) across up to max_levels levels that are
    within price_tolerance (0.1%) of the best price.

    Returns (best_price, total_notional).
    Raises IndexError if the book side is empty.
    """
    levels = book.get(side, [])
    if not levels:
        raise IndexError(f"Empty {side} side in order book")

    best_price = float(levels[0][0])
    total_notional = 0.0

    for i, (raw_price, raw_size) in enumerate(levels):
        if i >= max_levels:
            break
        price = float(raw_price)
        size  = float(raw_size)
        if abs(price - best_price) / best_price > price_tolerance:
            break   # price drifted too far from best — stop aggregating
        total_notional += price * size

    return best_price, total_notional


async def _watch_pair(
    binance: BinanceSpot,
    bybit: BybitSpot,
    pair: dict[str, str],
    state: BotState,
) -> None:
    """
    Continuously monitor a single spot pair for arbitrage gaps.
    Runs forever; exceptions are caught and logged.
    """
    unified  = pair["unified"]
    bn_symbol = pair["binance"]   # Use symbol directly from config (e.g. BTC/USDT)
    bb_symbol = pair["bybit"]     # Use symbol directly from config (e.g. BTC/USDT)

    logger.info(
        "[SpotGap] Watching {} — BN:{} / BB:{}",
        unified, bn_symbol, bb_symbol,
    )

    while True:
        try:
            # ── 1. Simultaneous order-book fetch ──────────────────────────
            # Binance: limit=5; Bybit spot valid values: [1,50,200,1000]
            bn_book, bb_book = await asyncio.gather(
                binance.watch_order_book(bn_symbol, limit=5),
                bybit.watch_order_book(bb_symbol, limit=50),
            )

            # ── 2. Extract best prices ────────────────────────────────────
            bn_ask, _ = _extract_top(bn_book, "asks")
            bb_bid, _ = _extract_top(bb_book, "bids")

            # ── 3. Crossed-book check ─────────────────────────────────────
            if bn_ask >= bb_bid:
                continue

            # ── 4. Liquidity check (aggregated across top 5 levels) ───────
            # Sum notional within 0.1% of the best price on each side so a
            # $1,000 leg can be filled even if spread across several levels.
            _, bn_notional = _aggregate_notional(bn_book, "asks")
            _, bb_notional = _aggregate_notional(bb_book, "bids")
            min_notional = min(bn_notional, bb_notional)

            if min_notional < MIN_LEG_NOTIONAL:
                logger.debug(
                    "[SpotGap] {} liquidity too low: ${:.0f} < ${:.0f}",
                    unified, min_notional, MIN_LEG_NOTIONAL,
                )
                continue

            # ── 5. Net spread + profit ────────────────────────────────────
            gross_spread = (bb_bid - bn_ask) / bn_ask
            net_spread = gross_spread - FEE_BUDGET
            dollar_profit = net_spread * LEG_SIZE_USD

            # ── 6. Time-sync check ────────────────────────────────────────
            bn_ts = bn_book.get("timestamp") or 0
            bb_ts = bb_book.get("timestamp") or 0

            # One-off startup clock-drift check against exchange time
            global _time_sync_checked
            if not _time_sync_checked and bn_ts:
                check_time_sync(bn_ts)
                _time_sync_checked = True

            diff_ms = ts_diff_ms(bn_ts, bb_ts)
            state.record_latency(diff_ms)

            if diff_ms > TIME_SYNC_THRESHOLD_MS:
                alert_latency_spike(unified, diff_ms, TIME_SYNC_THRESHOLD_MS)
                continue

            # ── 7. Alert ──────────────────────────────────────────────────
            logger.debug(
                "[SpotGap] {} crossed: bn_ask={:.4f} bb_bid={:.4f} "
                "gross={:.4f}% net={:.4f}% notional=${:.0f}",
                unified, bn_ask, bb_bid,
                gross_spread * 100, net_spread * 100, min_notional,
            )

            if net_spread > PROFIT_THRESHOLD:
                alert_spot_gap(
                    unified_symbol=unified,
                    binance_ask=bn_ask,
                    bybit_bid=bb_bid,
                    gross_spread_pct=gross_spread,
                    net_spread_pct=net_spread,
                    dollar_profit=dollar_profit,
                    latency_ms=diff_ms,
                    min_notional=min_notional,
                )
                state.record_gap(dollar_profit)

        except IndexError as exc:
            logger.debug("[SpotGap] {} empty book: {}", unified, exc)
            await asyncio.sleep(0.1)
        except Exception as exc:
            logger.error("[SpotGap] {} unexpected error: {}", unified, exc)
            await asyncio.sleep(1.0)


async def run_spot_gap_monitor(
    binance: BinanceSpot,
    bybit: BybitSpot,
    state: BotState,
) -> None:
    """
    Entry point: launch one watcher task per configured pair.
    All tasks run concurrently via asyncio.gather.
    """
    logger.info("[SpotGap] Starting monitor for {} pair(s)", len(SPOT_PAIRS))
    tasks = [
        _watch_pair(binance, bybit, pair, state)
        for pair in SPOT_PAIRS
    ]
    await asyncio.gather(*tasks)
