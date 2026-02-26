import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from crypt.bit import fetch_rsi_multi
from crypt.config import TICKERS, LONG_TICKERS
from crypt.orders_bit import place_short_order

# --- Constants ---
TABLE_TICKERS   = list(TICKERS.keys())
INTERVAL_LIMITS = {1: 1000, 15: 110}

# --- Auto-order persistence ---
_STATE_FILE = Path(__file__).parent / "auto_order_state.json"

# --- Mutable state (access via `import crypt.monitor as monitor`) ---
table_state:      dict    = {ticker: [] for ticker in TABLE_TICKERS}
detail_state:     dict    = {ticker: {iv: [] for iv in INTERVAL_LIMITS} for ticker in TABLE_TICKERS}
table_updated_at: str     = "—"

_auto_order_tickers: set[str] = set()
_placed_signal_keys: set[str] = set()
_dynamic_tickers:    set[str] = set()   # tickers added from overbought scan (not from config)


def set_dynamic_tickers(new_symbols: list[str]) -> dict:
    """Replace the dynamically-added ticker set with *new_symbols*.

    Config tickers (TICKERS) are never removed.
    Returns {'added': [...], 'removed': [...]}.
    """
    global _dynamic_tickers
    new_set    = set(new_symbols)
    to_remove  = _dynamic_tickers - new_set          # were dynamic, no longer needed
    config_set = set(TICKERS.keys())

    for sym in to_remove:
        if sym not in config_set and sym in TABLE_TICKERS:
            TABLE_TICKERS.remove(sym)
            table_state.pop(sym, None)
            detail_state.pop(sym, None)

    added = []
    for sym in new_symbols:
        if sym not in TABLE_TICKERS:
            TABLE_TICKERS.append(sym)
            table_state[sym]  = []
            detail_state[sym] = {iv: [] for iv in INTERVAL_LIMITS}
            added.append(sym)

    _dynamic_tickers = new_set
    return {"added": added, "removed": list(to_remove)}


# --- Auto-order state persistence ---

def _load_auto_order_state() -> None:
    global _auto_order_tickers
    if _STATE_FILE.exists():
        try:
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            _auto_order_tickers = set(data.get("enabled", []))
            logging.info("Auto-order state loaded: %s", _auto_order_tickers)
        except Exception as e:
            logging.warning("Could not load auto-order state: %s", e)


def _save_auto_order_state() -> None:
    try:
        _STATE_FILE.write_text(
            json.dumps({"enabled": sorted(_auto_order_tickers)}, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logging.warning("Could not save auto-order state: %s", e)


# --- Frontend data formatting ---

def _fmt_multi(r: dict) -> dict:
    """Format a raw fetch_rsi_multi record for frontend consumption."""
    def _rnd(v, n=5): return round(v, n) if v is not None else None
    return {
        "time":                      r["time"].strftime("%Y-%m-%d %H:%M"),
        "price":                     r["price"],
        "rsi_15m":                   round(r["rsi_15m"], 2),
        "rsi_1h":                    _rnd(r["rsi_1h"], 2),
        "rsi_4h":                    _rnd(r["rsi_4h"], 2),
        "rsi_1d":                    _rnd(r["rsi_1d"], 2),
        "day_high_so_far":           _rnd(r.get("day_high_so_far")),
        "day_low_so_far":            _rnd(r.get("day_low_so_far")),
        "is_short":                  r["is_short"],
        "is_long":                   r.get("is_long", False),
        "potential_profit_pct":      r["potential_profit_pct"],
        "current_profit_pct":        r["current_profit_pct"],
        "long_potential_profit_pct": r.get("long_potential_profit_pct"),
        "long_current_profit_pct":   r.get("long_current_profit_pct"),
    }


# --- Background refresh ---

async def refresh_tables() -> None:
    global table_updated_at
    for ticker in TABLE_TICKERS:
        criteria      = TICKERS.get(ticker)
        long_criteria = LONG_TICKERS.get(ticker)
        for interval, lim in INTERVAL_LIMITS.items():
            try:
                records = await asyncio.to_thread(
                    fetch_rsi_multi, ticker, criteria, long_criteria, interval, lim
                )

                if interval == 15:
                    table_state[ticker] = [
                        {
                            "time":  r["time"].strftime("%Y-%m-%d %H:%M"),
                            "price": r["price"],
                            "rsi":   round(r["rsi_15m"], 2),
                        }
                        for r in records
                    ]

                    if ticker in _auto_order_tickers and records:
                        latest = records[-1]
                        if latest.get("is_short"):
                            key = f"{ticker}:{latest['time'].strftime('%Y-%m-%d %H:%M')}"
                            if key not in _placed_signal_keys:
                                _placed_signal_keys.add(key)
                                try:
                                    result = await asyncio.to_thread(
                                        place_short_order, ticker, latest["price"]
                                    )
                                    logging.info("Order placed for %s: %s", ticker, result)
                                except Exception as oe:
                                    logging.error("Order placement failed for %s: %s", ticker, oe)

                detail_state[ticker][interval] = [_fmt_multi(r) for r in reversed(records)]

            except Exception as e:
                print(f"Table fetch error [{ticker} {interval}m]: {e}")

    table_updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def table_monitor() -> None:
    while True:
        await asyncio.sleep(60)
        await refresh_tables()
