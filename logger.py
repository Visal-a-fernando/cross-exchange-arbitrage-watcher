"""
utils/logger.py — Loguru setup with colorful structured output.
"""

import sys
from loguru import logger
from config import LOG_LEVEL, LOG_FILE


def setup_logger() -> None:
    """Configure loguru sinks: stderr (coloured) + rotating file."""
    logger.remove()  # Remove default sink

    # ── Console sink ────────────────────────────────────────────────────────
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        colorize=True,
        format=(
            "<green>{time:HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
            "<level>{message}</level>"
        ),
        backtrace=True,
        diagnose=True,
    )

    # ── File sink (rotating, no colour codes) ───────────────────────────────
    logger.add(
        LOG_FILE,
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function} | {message}",
        backtrace=True,
        diagnose=False,
        enqueue=True,   # Thread-safe async writing
    )

    logger.info("Logger initialised — level={}", LOG_LEVEL)
