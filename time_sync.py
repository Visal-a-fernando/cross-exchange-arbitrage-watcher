"""
utils/time_sync.py — Timestamp comparison and latency utilities.

Provides:
  - ts_diff_ms(ts_a, ts_b):  absolute difference in milliseconds
  - wall_clock_ms():          current time as Unix epoch milliseconds
  - check_time_sync():        one-off NTP drift check at startup

VPS Deployment Note:
  Before deploying to AWS Tokyo, sync the system clock:
    Linux:   sudo ntpdate -s time.nist.gov
    Windows: w32tm /resync
  A drifted clock will cause false [LATENCY SPIKE] warnings and missed
  arb signals because exchange timestamps are UTC-anchored.
"""

from __future__ import annotations

import time
from typing import Optional

from loguru import logger

# Max acceptable local-clock drift vs exchange timestamp at startup (ms)
_STARTUP_DRIFT_WARN_MS = 500


def wall_clock_ms() -> int:
    """Return current UTC epoch time in milliseconds."""
    return int(time.time() * 1000)


def ts_diff_ms(ts_a: Optional[int], ts_b: Optional[int]) -> float:
    """
    Compute |ts_a - ts_b| in milliseconds.

    If either timestamp is None or zero (exchange didn't provide one),
    returns 0.0 so the caller can still proceed without penalty.
    """
    if not ts_a or not ts_b:
        return 0.0
    return abs(float(ts_a) - float(ts_b))


def check_time_sync(exchange_ts_ms: int) -> None:
    """
    Compare the local wall clock to an exchange-provided timestamp.
    Logs a WARNING if drift exceeds _STARTUP_DRIFT_WARN_MS.

    Call once after the first order-book message arrives.
    """
    local_ms = wall_clock_ms()
    drift = abs(local_ms - exchange_ts_ms)
    if drift > _STARTUP_DRIFT_WARN_MS:
        logger.warning(
            "[TimeSync] Local clock drift = {:.0f}ms vs exchange. "
            "Consider running: sudo ntpdate -s time.nist.gov",
            drift,
        )
    else:
        logger.debug("[TimeSync] Clock drift OK: {:.0f}ms", drift)
