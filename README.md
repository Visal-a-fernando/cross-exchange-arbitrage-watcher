# Watcher Bot - Phase 1 (Read Only)

Async Python arbitrage watcher for Binance ↔ Bybit spot & perpetual markets.  
**No trade execution. Strictly observation and alerting.**

---

## Strategy Overview

| Capital | Target | Fee edge |
|---|---|---|
| $2,000 ($1k each exchange) | $200/month (10% ROI) | Binance "United Stables (U)" promo: BTC/U and ETH/U at **0.00% fee** (Apr - Jul 2026) |

**Profit threshold:** A 0.15% net spread on a $1,000 leg yields ≈$1.50 profit after fees.

**Total friction budget:** 0.08% (Bybit taker 0.06% + 0.02% slippage buffer).

---

## Architecture

```
main.py
  ├── spot_gap_monitor          ← WebSocket order-book scanner (asyncio.gather)
  ├── funding_carry_monitor     ← REST polling every 60s (polite, 1s gap)
  ├── dashboard_task            ← Terminal refresh every 60s
  ├── midnight_reset_task       ← Resets daily P&L counters at UTC 00:00
  └── health_check_task         ← Heartbeat log every 5 minutes
```

```
.
├── config.py                   ← Master DEBUG_MODE toggle
├── main.py                     ← Async entry point
├── exchanges/
│   ├── base.py                 ← BaseExchange (precision, WS wrapper)
│   ├── binance.py              ← BinanceSpot + BinanceFutures
│   └── bybit.py                ← BybitSpot + BybitPerpetual
├── strategies/
│   ├── spot_gap.py             ← Spot arbitrage monitor (5A)
│   └── funding_carry.py        ← Funding divergence monitor (5B)
└── utils/
    ├── logger.py               ← Loguru: coloured console + rotating file
    ├── symbols.py              ← BTC/U ↔ BTC/USDT normaliser
    ├── notifier.py             ← BRIGHT GREEN / CYAN alerts + Telegram stub
    ├── dashboard.py            ← 10-line terminal status dashboard
    ├── state.py                ← Shared BotState dataclass
    ├── time_sync.py            ← Timestamp delta + NTP drift checker
    └── midnight_reset.py       ← UTC midnight daily counter reset
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# API keys are OPTIONAL - public WebSocket works without them
# Fill in TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID for Phase 2 alerts
```

### 3. Run (Perth - DEBUG mode)

```bash
python main.py
```

---

## DEBUG_MODE Toggle

Open `config.py` and set the flag at the top:

```python
DEBUG_MODE = True   # Perth local testing
DEBUG_MODE = False  # AWS Tokyo production
```

| Behaviour | DEBUG = True | DEBUG = False |
|---|---|---|
| Alert prefix | `[SIMULATED SPOT GAP]` | `[SPOT GAP]` |
| Funding prefix | `[SIMULATED FUNDING CARRY]` | `[FUNDING CARRY]` |
| Time-sync threshold | 1000 ms | 200 ms |
| Telegram | Suppressed | Enabled (if token set) |
| Dashboard label | `RUNNING (Perth - DEBUG)` | `RUNNING (Tokyo ap-northeast-1)` |

---

## Alert Examples

**Spot Gap (BRIGHT GREEN):**
```
[SIMULATED SPOT GAP] BTC-USD | BN ask=62450.123456  BB bid=62545.000000 |
gross=0.1519%  net=0.0719% | profit≈$0.72 | liquidity=$8,340 | Δt=38ms
```

**Funding Carry (CYAN):**
```
[SIMULATED FUNDING CARRY] LRC-USD | BN rate=0.00100%  BB rate=0.04200% |
spread=0.04100% | est. APR≈44.9%
```

**Latency Spike (YELLOW):**
```
[LATENCY SPIKE] BTC-USD | Δt=1243ms > threshold=1000ms - skipping tick
```

**Dashboard (every 60s):**
```
╔═════════════════════════════════════════════════════╗
║            WATCHER BOT - STATUS DASHBOARD           ║
╚═════════════════════════════════════════════════════╝
  TIME  2026-04-17 14:32:01 UTC
  ──────────────────────────────────────────────────────
  CAPITAL  Binance $1,000.00  │  Bybit $1,000.00
  P&L     Net Profit Today: $4.20
  GAPS    Spotted Today: 14  │  Avg Latency: 42ms
  STATUS  RUNNING (Tokyo ap-northeast-1)  [LIVE]
  ──────────────────────────────────────────────────────
```

---

## AWS Tokyo Deployment Checklist

- [ ] Sync system clock: `sudo ntpdate -s time.nist.gov`
- [ ] Set `DEBUG_MODE = False` in `config.py`
- [ ] Set `DEPLOY_REGION=Tokyo ap-northeast-1` in `.env`
- [ ] Set `export AIOHTTP_CLIENT_DNS_CACHE=false` in `.bashrc` or systemd unit
- [ ] Fill in Telegram credentials in `.env` for live alerts
- [ ] Run: `python main.py`
- [ ] Check `logs/watcher.log` for errors on first startup

### Recommended systemd unit (`/etc/systemd/system/watcher.service`):

```ini
[Unit]
Description=Watcher Bot - Crypto Arb Monitor
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/home/ubuntu/watcher_bot
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=10
Environment=AIOHTTP_CLIENT_DNS_CACHE=false
EnvironmentFile=/home/ubuntu/watcher_bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable watcher
sudo systemctl start watcher
sudo journalctl -u watcher -f    # tail logs
```

---

## Phase 2 Roadmap

- [ ] Enable Telegram alerts (fill `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`)
- [ ] Pull live balances from exchange REST APIs
- [ ] Add z-score filter on funding spreads (rolling 24h window via pandas)
- [ ] Add ETH gas spike guard for cross-chain arb paths
- [ ] Build execution engine (Phase 2 - separate repo)

---

## Safety Notes

- `create_order()` is **never called** anywhere in this codebase.
- No funds are at risk. This is a pure observation bot.
- API keys are optional and only improve balance polling accuracy.
