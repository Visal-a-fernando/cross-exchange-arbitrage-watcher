"""
strategies/funding_carry.py — Funding Rate Divergence Monitor (Section 5B).

Algorithm:
  - Poll Binance Perp and Bybit Perp funding rates every 60 seconds.
  - asyncio.sleep(1.0) between exchange calls to be polite.
  - funding_spread = bybit_rate - binance_rate
  - Alert if spread > 0.0003 (0.03%)
  - Estimate APR: spread * 3 * 365 * 100  (funding paid 3×/day)

Pairs monitored: LRC/USDT, BERA/USDT (configurable in config.py).
"""

from __future__ import annotations

import asyncio
from typing import Optional

import pandas as pd
from loguru import logger

from config import (
    FUNDING_PAIRS,
    FUNDING_POLL_INTERVAL_S,
    FUNDING_SPREAD_THRESHOLD,
    LEG_SIZE_USD,
)
from exchanges.binance import BinanceFutures
from exchanges.bybit import BybitPerpetual
from utils.notifier import alert_funding_carry
from utils.state import BotState

# Funding is typically paid 3× per day on most perps
FUNDING_PERIODS_PER_DAY = 3


def _extract_rate(data: dict) -> Optional[float]:
    """Safely extract fundingRate from a ccxt fetchFundingRate response."""
    if not data:
        return None
    rate = data.get("fundingRate")
    if rate is None:
        # Some exchanges nest under 'info'
        rate = data.get("info", {}).get("fundingRate")
    try:
        return float(rate) if rate is not None else None
    except (ValueError, TypeError):
        return None


def _estimate_apr(spread: float) -> float:
    """Convert per-period funding spread to rough annualised % return."""
    return spread * FUNDING_PERIODS_PER_DAY * 365 * 100


async def _poll_pair(
    bn_futures: BinanceFutures,
    bb_perp: BybitPerpetual,
    pair: dict[str, str],
    state: BotState,
) -> None:
    """Fetch and compare funding rates for a single pair, then emit alert."""
    unified = pair["unified"]
    bn_sym = pair["binance"]
    bb_sym = pair["bybit"]

    # Polite: 1-second gap between exchange calls
    bn_data = await bn_futures.fetch_funding_rate(bn_sym)
    await asyncio.sleep(1.0)
    bb_data = await bb_perp.fetch_funding_rate(bb_sym)

    bn_rate = _extract_rate(bn_data)
    bb_rate = _extract_rate(bb_data)

    if bn_rate is None or bb_rate is None:
        logger.debug(
            "[FundingCarry] {} — could not parse rates: BN={} BB={}",
            unified, bn_data, bb_data,
        )
        return

    funding_spread = bb_rate - bn_rate
    dollar_per_period = funding_spread * LEG_SIZE_USD

    logger.debug(
        "[FundingCarry] {} BN={:.5f}% BB={:.5f}% spread={:.5f}% carry=${:.3f}/period",
        unified, bn_rate * 100, bb_rate * 100, funding_spread * 100, dollar_per_period,
    )

    if funding_spread > FUNDING_SPREAD_THRESHOLD:
        apr = _estimate_apr(funding_spread)
        alert_funding_carry(
            unified_symbol=unified,
            binance_rate=bn_rate,
            bybit_rate=bb_rate,
            funding_spread=funding_spread,
            apr_pct=apr,
            dollar_per_period=dollar_per_period,
        )
        state.record_gap(dollar_per_period)


async def run_funding_carry_monitor(
    bn_futures: BinanceFutures,
    bb_perp: BybitPerpetual,
    state: BotState,
) -> None:
    """
    Entry point: poll all configured funding pairs every FUNDING_POLL_INTERVAL_S.

    Uses a pandas DataFrame to maintain a rolling history of spreads
    (useful for future z-score filtering or trend analysis).
    """
    logger.info(
        "[FundingCarry] Starting monitor — polling every {}s for {} pair(s)",
        FUNDING_POLL_INTERVAL_S,
        len(FUNDING_PAIRS),
    )

    # Rolling history: indexed by datetime, columns = unified symbol strings
    history: pd.DataFrame = pd.DataFrame()

    while True:
        for pair in FUNDING_PAIRS:
            try:
                await _poll_pair(bn_futures, bb_perp, pair, state)
            except Exception as exc:
                logger.error(
                    "[FundingCarry] {} unhandled error: {}", pair["unified"], exc
                )

        # Wait before next full poll cycle
        await asyncio.sleep(FUNDING_POLL_INTERVAL_S)
