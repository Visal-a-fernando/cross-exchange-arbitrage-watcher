"""
utils/dashboard.py — Terminal status summary renderer.

Renders a clean 10-line dashboard every DASHBOARD_REFRESH_S seconds.
Uses ANSI escape codes to clear and redraw in-place without disrupting
the live alert stream that scrolls above.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from config import DEBUG_MODE, DEPLOY_REGION, DASHBOARD_REFRESH_S

if TYPE_CHECKING:
    from utils.state import BotState

# ── ANSI codes ───────────────────────────────────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_WHITE  = "\033[97m"
_BG_BAR = "\033[48;5;234m"   # very dark grey background for the bar lines

_BAR = f"{_BG_BAR}{'-' * 55}{_RESET}"


def _fmt_usd(val: float) -> str:
    return f"${val:,.2f}"


def render_dashboard(state: "BotState") -> str:
    """
    Build the dashboard string.

    Args:
        state: shared BotState dataclass (see utils/state.py)

    Returns:
        Multi-line string ready to print.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    status_label = f"RUNNING ({DEPLOY_REGION})"
    mode_tag = f"{_YELLOW}[DEBUG]{_RESET}" if DEBUG_MODE else f"{_GREEN}[LIVE]{_RESET}"

    avg_lat = (
        f"{state.avg_latency_ms:.0f}ms"
        if state.avg_latency_ms is not None
        else "n/a"
    )

    lines = [
        "",
        f"{_BOLD}{_CYAN}+{'=' * 53}+{_RESET}",
        f"{_BOLD}{_CYAN}|{'  WATCHER BOT -- STATUS DASHBOARD':^53}|{_RESET}",
        f"{_BOLD}{_CYAN}+{'=' * 53}+{_RESET}",
        f"  {_DIM}TIME{_RESET}  {_WHITE}{now_utc}{_RESET}",
        _BAR,
        f"  {_DIM}CAPITAL{_RESET}  Binance {_GREEN}{_fmt_usd(state.binance_balance)}{_RESET}"
        f"  |  Bybit {_GREEN}{_fmt_usd(state.bybit_balance)}{_RESET}",
        f"  {_DIM}P&L{_RESET}     Net Profit Today: {_GREEN}{_fmt_usd(state.net_profit_today)}{_RESET}",
        f"  {_DIM}GAPS{_RESET}    Spotted Today: {_YELLOW}{state.gaps_today}{_RESET}"
        f"  |  Avg Latency: {_CYAN}{avg_lat}{_RESET}",
        f"  {_DIM}STATUS{_RESET}  {status_label}  {mode_tag}",
        _BAR,
        "",
    ]
    return "\n".join(lines)


def print_dashboard(state: "BotState") -> None:
    """
    Clear the terminal and reprint the dashboard at the top.

    Note: We use os.system('clear'/'cls') for a hard refresh.
    On AWS Tokyo this avoids partial ANSI artefacts on xterm-256color.
    """
    os.system("cls" if os.name == "nt" else "clear")
    print(render_dashboard(state))
    sys.stdout.flush()
