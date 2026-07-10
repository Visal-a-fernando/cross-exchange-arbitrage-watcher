"""
utils/midnight_reset.py — Resets daily counters in BotState at UTC midnight.

Runs as a background asyncio task. Calculates the exact number of seconds
until the next midnight UTC, sleeps until then, resets, then loops.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger

from utils.state import BotState


def _seconds_until_midnight_utc() -> float:
    """Return the number of seconds from now until 00:00:00 UTC tomorrow."""
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (tomorrow - now).total_seconds()


async def midnight_reset_task(state: BotState) -> None:
    """
    Background task: sleep until midnight UTC, reset daily P&L counters, repeat.
    """
    while True:
        sleep_secs = _seconds_until_midnight_utc()
        logger.info(
            "[MidnightReset] Next reset in {:.0f}s ({:.1f}h)",
            sleep_secs,
            sleep_secs / 3600,
        )
        await asyncio.sleep(sleep_secs)

        # ── Reset daily counters ─────────────────────────────────────────
        prev_gaps   = state.gaps_today
        prev_profit = state.net_profit_today

        state.gaps_today        = 0
        state.net_profit_today  = 0.0
        state.latency_samples   = []

        logger.info(
            "[MidnightReset] Daily counters reset. "
            "Yesterday: {} gaps | ${:.2f} profit",
            prev_gaps,
            prev_profit,
        )
