"""
utils/notifier.py — Console alerts + Telegram stub.

Respects DEBUG_MODE:
  - In DEBUG mode: prefixes [SIMULATED SPOT GAP] / [SIMULATED FUNDING CARRY],
    suppresses Telegram.
  - In production: prefixes [SPOT GAP] / [FUNDING CARRY],
    sends Telegram (stub — Phase 2).
"""

from __future__ import annotations

import aiohttp
from loguru import logger
from config import DEBUG_MODE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED

# ── ANSI colour codes ────────────────────────────────────────────────────────
_RESET   = "\033[0m"
_BRIGHT_GREEN = "\033[92;1m"
_CYAN    = "\033[96m"
_YELLOW  = "\033[93m"
_RED     = "\033[91m"
_DIM     = "\033[2m"

# ── Label prefixes ───────────────────────────────────────────────────────────
_SPOT_LABEL    = "[SIMULATED SPOT GAP]"    if DEBUG_MODE else "[SPOT GAP]"
_FUNDING_LABEL = "[SIMULATED FUNDING CARRY]" if DEBUG_MODE else "[FUNDING CARRY]"
_LATENCY_LABEL = "[LATENCY SPIKE]"


def alert_spot_gap(
    unified_symbol: str,
    binance_ask: float,
    bybit_bid: float,
    gross_spread_pct: float,
    net_spread_pct: float,
    dollar_profit: float,
    latency_ms: float,
    min_notional: float,
) -> None:
    """Print a BRIGHT GREEN spot-gap alert to stdout."""
    label = _SPOT_LABEL
    msg = (
        f"{_BRIGHT_GREEN}{label}{_RESET} "
        f"{unified_symbol} | "
        f"BN ask={binance_ask:.6f}  BB bid={bybit_bid:.6f} | "
        f"gross={gross_spread_pct*100:.4f}%  net={net_spread_pct*100:.4f}% | "
        f"profit≈${dollar_profit:.2f} | "
        f"liquidity=${min_notional:,.0f} | "
        f"Δt={latency_ms:.1f}ms"
    )
    print(msg)
    logger.info("{} {}", label, msg.replace(_BRIGHT_GREEN, "").replace(_RESET, ""))


def alert_funding_carry(
    unified_symbol: str,
    binance_rate: float,
    bybit_rate: float,
    funding_spread: float,
    apr_pct: float,
    dollar_per_period: float,
) -> None:
    """Print a CYAN funding-carry alert to stdout."""
    label = _FUNDING_LABEL
    body = (
        f"{unified_symbol} | "
        f"BN rate={binance_rate*100:.5f}%  BB rate={bybit_rate*100:.5f}% | "
        f"spread={funding_spread*100:.5f}% | "
        f"carry≈${dollar_per_period:.2f}/period | "
        f"est. APR≈{apr_pct:.1f}%"
    )
    print(f"{_CYAN}{label}{_RESET} {body}")
    logger.info("{} {}", label, body)


def alert_latency_spike(symbol: str, diff_ms: float, threshold_ms: int) -> None:
    """Print a YELLOW latency-spike warning."""
    msg = (
        f"{_YELLOW}{_LATENCY_LABEL}{_RESET} "
        f"{symbol} | Δt={diff_ms:.1f}ms > threshold={threshold_ms}ms — skipping tick"
    )
    print(msg)
    logger.warning("{}", msg.replace(_YELLOW, "").replace(_RESET, ""))


async def send_telegram(text: str) -> None:
    """
    Send a Telegram message.
    Phase 1: stub — logs intent, does not send in DEBUG mode.
    Phase 2: enable by setting TELEGRAM_ENABLED=True and providing credentials.
    """
    if not TELEGRAM_ENABLED:
        logger.debug("[TG-STUB] Would send: {}", text[:80])
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    logger.warning("Telegram API error: status={}", resp.status)
    except Exception as exc:
        logger.error("Telegram send failed: {}", exc)
