"""
config.py — Central configuration for the Watcher Bot.

Toggle DEBUG_MODE before deployment:
  True  → Perth local testing  (relaxed checks, simulated labels, no Telegram)
  False → AWS Tokyo production  (strict checks, live labels, Telegram enabled)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
#  MASTER TOGGLE
# ──────────────────────────────────────────────
DEBUG_MODE: bool = True   # ← flip to False before deploying to Tokyo

# ──────────────────────────────────────────────
#  TIME-SYNC THRESHOLDS (ms)
# ──────────────────────────────────────────────
TIME_SYNC_THRESHOLD_MS: int = 5000 if DEBUG_MODE else 200

# ──────────────────────────────────────────────
#  PROFIT PARAMETERS
# ──────────────────────────────────────────────
TOTAL_CAPITAL_USD: float = 2_000.0          # $1k Binance + $1k Bybit
LEG_SIZE_USD: float = 1_000.0               # Single-leg trade size
FEE_BUDGET: float = 0.0008                  # 0.06% Bybit taker + 0.02% slippage
PROFIT_THRESHOLD: float = 0.0015           # 0.15% net spread → ~$1.50 on $1k leg
MIN_LEG_NOTIONAL: float = 0.0              # Phase 1: disabled (read-only, no execution risk)

# ──────────────────────────────────────────────
#  MONITORED SYMBOLS
# ──────────────────────────────────────────────
# Spot arbitrage pairs (Binance uses 'U' stablecoin during promo)
SPOT_PAIRS = [
    {"binance": "BTC/USDT",  "bybit": "BTC/USDT",  "unified": "BTC-USD"},
    {"binance": "ETH/USDT",  "bybit": "ETH/USDT",  "unified": "ETH-USD"},
    {"binance": "LRC/USDT",  "bybit": "LRC/USDT",  "unified": "LRC-USD"},
    {"binance": "BERA/USDT", "bybit": "BERA/USDT", "unified": "BERA-USD"},
]

# Note on Binance "United Stables (U)" promotion (April–July 2026):
# BTC/U and ETH/U have 0.00% maker/taker fees on Binance Spot.
# The symbol mapping below handles U ↔ USDT normalisation.
BINANCE_U_PAIRS = {
    "BTC/USDT": "BTC/U",
    "ETH/USDT": "ETH/U",
}

# Funding rate divergence pairs
FUNDING_PAIRS = [
    {"unified": "LRC-USD",  "binance": "LRC/USDT", "bybit": "LRC/USDT:USDT"},
    {"unified": "BERA-USD", "binance": "BERA/USDT", "bybit": "BERA/USDT:USDT"},
]

FUNDING_POLL_INTERVAL_S: int = 60          # Seconds between funding polls
FUNDING_SPREAD_THRESHOLD: float = 0.00005  # 0.005% → captures the persistent LRC 0.01% Bybit premium

# ──────────────────────────────────────────────
#  DASHBOARD
# ──────────────────────────────────────────────
DASHBOARD_REFRESH_S: int = 60

# ──────────────────────────────────────────────
#  DEPLOYMENT INFO
# ──────────────────────────────────────────────
DEPLOY_REGION: str = os.getenv(
    "DEPLOY_REGION",
    "Perth - DEBUG" if DEBUG_MODE else "Tokyo ap-northeast-1",
)

# ──────────────────────────────────────────────
#  EXCHANGE CREDENTIALS (optional — public WS works without keys)
# ──────────────────────────────────────────────
BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
BYBIT_API_KEY: str = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET: str = os.getenv("BYBIT_API_SECRET", "")

# ──────────────────────────────────────────────
#  TELEGRAM (Phase 2 stub)
# ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED: bool = (not DEBUG_MODE) and bool(TELEGRAM_BOT_TOKEN)

# ──────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────
LOG_LEVEL: str = "DEBUG" if DEBUG_MODE else "INFO"
LOG_FILE: str = "logs/watcher.log"
