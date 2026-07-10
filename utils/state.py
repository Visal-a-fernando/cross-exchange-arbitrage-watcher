"""
utils/state.py — Shared mutable state passed across async tasks.

All fields are updated in-place; no locking needed because Python's GIL
protects simple attribute assignments in asyncio single-thread loops.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BotState:
    # ── Balances (fixed/simulated for Phase 1) ──────────────────────────────
    binance_balance: float = 1_000.0
    bybit_balance: float = 1_000.0

    # ── Daily counters (reset at midnight UTC) ──────────────────────────────
    gaps_today: int = 0
    net_profit_today: float = 0.0

    # ── Latency tracking ────────────────────────────────────────────────────
    latency_samples: list[float] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> Optional[float]:
        if not self.latency_samples:
            return None
        return sum(self.latency_samples) / len(self.latency_samples)

    def record_latency(self, diff_ms: float) -> None:
        self.latency_samples.append(abs(diff_ms))
        # Keep last 500 samples to avoid unbounded growth
        if len(self.latency_samples) > 500:
            self.latency_samples = self.latency_samples[-500:]

    def record_gap(self, dollar_profit: float) -> None:
        self.gaps_today += 1
        self.net_profit_today += dollar_profit
