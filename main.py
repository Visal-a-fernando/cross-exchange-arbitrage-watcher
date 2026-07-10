"""
main.py — Watcher Bot entry point.

Launches three concurrent async tasks:
  1. Spot Gap Monitor     — real-time WebSocket order-book scanner
  2. Funding Carry Monitor — polite REST polling for funding divergence
  3. Dashboard Task        — terminal status summary every 60 seconds

Phase 1: READ ONLY. No trade execution.

─────────────────────────────────────────────────────────────────────
VPS Deployment Notes (AWS Tokyo ap-northeast-1):
─────────────────────────────────────────────────────────────────────
1. Clock sync BEFORE starting the bot:
   Linux:   sudo ntpdate -s time.nist.gov
   Windows: w32tm /resync

2. Set this env var to reduce DNS lookup overhead on Tokyo:
   export AIOHTTP_CLIENT_DNS_CACHE=false

3. Flip config.py → DEBUG_MODE = False before deploying.
─────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path

# ── Fix import path FIRST — before any local module imports ──────────────────
# This ensures 'exchanges', 'strategies', 'utils' are all findable on Windows.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Windows DNS fix ───────────────────────────────────────────────────────────
# aiodns (pycares) cannot contact DNS servers on Windows with SelectorEventLoop.
# Patch TCPConnector to default to ThreadedResolver so aiohttp/ccxt use the OS resolver.
import aiohttp

_orig_connector_init = aiohttp.TCPConnector.__init__

def _patched_connector_init(self, *args, resolver=None, **kwargs):  # type: ignore[override]
    if resolver is None:
        resolver = aiohttp.ThreadedResolver()
    _orig_connector_init(self, *args, resolver=resolver, **kwargs)

aiohttp.TCPConnector.__init__ = _patched_connector_init  # type: ignore[method-assign]

from loguru import logger

# ── Local imports ─────────────────────────────────────────────────────────────
from config import DEBUG_MODE, DASHBOARD_REFRESH_S, DEPLOY_REGION
from exchanges.binance import BinanceFutures, BinanceSpot
from exchanges.bybit import BybitPerpetual, BybitSpot
from strategies.funding_carry import run_funding_carry_monitor
from strategies.spot_gap import run_spot_gap_monitor
from utils.dashboard import print_dashboard
from utils.logger import setup_logger
from utils.midnight_reset import midnight_reset_task
from utils.state import BotState

# ── Create logs directory ─────────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)
setup_logger()


# ─────────────────────────────────────────────────────────────────────────────
#  Health-check background task
# ─────────────────────────────────────────────────────────────────────────────

async def _health_check_task(state: BotState) -> None:
    """
    Log a brief heartbeat every 5 minutes so operators know the bot
    is alive even during quiet market periods with no gap alerts.
    """
    INTERVAL = 300  # seconds
    while True:
        await asyncio.sleep(INTERVAL)
        avg = state.avg_latency_ms
        lat_str = f"{avg:.0f}ms" if avg is not None else "n/a"
        logger.info(
            "[Heartbeat] gaps={} | profit=${:.2f} | avg_latency={}",
            state.gaps_today,
            state.net_profit_today,
            lat_str,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Dashboard background task
# ─────────────────────────────────────────────────────────────────────────────

async def dashboard_task(state: BotState) -> None:
    """
    Refresh the terminal dashboard every DASHBOARD_REFRESH_S seconds.
    Does NOT clear the scroll-back buffer — uses os.system('clear')
    to hard-reset the visible screen, preserving alert history in the
    terminal's scroll buffer.
    """
    logger.info("[Dashboard] Task started — refreshing every {}s", DASHBOARD_REFRESH_S)
    while True:
        try:
            print_dashboard(state)
        except Exception as exc:
            logger.warning("[Dashboard] Render error: {}", exc)
        await asyncio.sleep(DASHBOARD_REFRESH_S)


# ─────────────────────────────────────────────────────────────────────────────
#  Graceful shutdown
# ─────────────────────────────────────────────────────────────────────────────

_shutdown_event = asyncio.Event()


def _handle_signal(*_: object) -> None:
    logger.warning("Shutdown signal received — stopping bot...")
    _shutdown_event.set()


# ─────────────────────────────────────────────────────────────────────────────
#  Main coroutine
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    mode_label = "DEBUG (Perth local)" if DEBUG_MODE else f"PRODUCTION ({DEPLOY_REGION})"
    logger.info("=" * 60)
    logger.info("  Watcher Bot starting — mode: {}", mode_label)
    logger.info("  Phase 1 — READ ONLY. No trade execution.")
    logger.info("=" * 60)

    # ── Register OS signals for graceful shutdown ─────────────────────────
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Windows does not support add_signal_handler for SIGTERM
            pass

    # ── Shared state ──────────────────────────────────────────────────────
    state = BotState()

    # ── Initialise exchange connections ───────────────────────────────────
    bn_spot = BinanceSpot()
    bb_spot = BybitSpot()
    bn_futures = BinanceFutures()
    bb_perp = BybitPerpetual()

    exchanges = [bn_spot, bb_spot, bn_futures, bb_perp]

    logger.info("Connecting to exchanges...")
    try:
        for exc in exchanges:
            await exc.connect()
    except Exception as e:
        logger.critical("Failed to connect to exchanges: {}", e)
        logger.critical("Check your internet connection and exchange availability.")
        sys.exit(1)

    logger.info("All exchanges connected. Launching monitor tasks...")

    # ── Build task set ────────────────────────────────────────────────────
    tasks = [
        asyncio.create_task(
            run_spot_gap_monitor(bn_spot, bb_spot, state),
            name="spot_gap",
        ),
        asyncio.create_task(
            run_funding_carry_monitor(bn_futures, bb_perp, state),
            name="funding_carry",
        ),
        asyncio.create_task(
            dashboard_task(state),
            name="dashboard",
        ),
        asyncio.create_task(
            midnight_reset_task(state),
            name="midnight_reset",
        ),
        asyncio.create_task(
            _health_check_task(state),
            name="health_check",
        ),
        asyncio.create_task(
            _shutdown_event.wait(),
            name="shutdown_sentinel",
        ),
    ]

    # ── Run until shutdown sentinel fires ────────────────────────────────
    done, pending = await asyncio.wait(
        tasks,
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Shutdown sentinel completed (SIGINT / SIGTERM)
    logger.info("Shutting down — cancelling {} task(s)...", len(pending))
    for task in pending:
        task.cancel()

    await asyncio.gather(*pending, return_exceptions=True)

    # ── Close all exchange connections cleanly ────────────────────────────
    logger.info("Closing exchange connections...")
    for exc in exchanges:
        await exc.close()

    logger.info("Watcher Bot stopped cleanly. Goodbye.")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Windows: use SelectorEventLoop to avoid ProactorEventLoop WS issues
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")