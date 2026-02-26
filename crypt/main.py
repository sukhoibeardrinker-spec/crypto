import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import Body, FastAPI, Request
from fastapi.templating import Jinja2Templates

import crypt.monitor as monitor
import crypt.overbought as overbought
from crypt.bit import session as bybit_session
from crypt.orders_bit import place_short_order
from crypt.config import TICKERS, LONG_TICKERS, OVERBOUGHT_THRESHOLDS, ShortCriteria, LongCriteria

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "front")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    monitor._load_auto_order_state()
    await monitor.refresh_tables()
    asyncio.create_task(monitor.table_monitor())
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(request=request, name="main.html", context={})


@app.get("/api/table")
async def table_json():
    return {
        "tickers":    monitor.TABLE_TICKERS,
        "data":       monitor.table_state,
        "updated_at": monitor.table_updated_at,
    }


@app.get("/api/ticker/{symbol}")
async def ticker_detail(symbol: str, interval: int = 15):
    if symbol not in monitor.TABLE_TICKERS:
        return {"error": f"Unknown ticker: {symbol}"}
    if interval not in monitor.INTERVAL_LIMITS:
        return {"error": f"Unsupported interval: {interval}. Use one of {list(monitor.INTERVAL_LIMITS)}"}
    criteria      = TICKERS.get(symbol)      or ShortCriteria()
    long_criteria = LONG_TICKERS.get(symbol) or LongCriteria()
    return {
        "ticker":        symbol,
        "interval":      interval,
        "data":          monitor.detail_state.get(symbol, {}).get(interval, []),
        "updated_at":    monitor.table_updated_at,
        "criteria":      asdict(criteria),
        "long_criteria": asdict(long_criteria),
    }


@app.post("/api/short/{symbol}")
async def manual_short(
    symbol:   str,
    tp_pct:   float = 0.02,
    sl_pct:   float = 0.10,
    amount:   float = 10.0,
    leverage: int   = 1,
):
    """Place a manual SHORT order at the latest 1m price for the given ticker."""
    if symbol not in monitor.TABLE_TICKERS:
        return {"error": f"Unknown ticker: {symbol}"}
    rows = monitor.detail_state.get(symbol, {}).get(1, [])
    if not rows:
        return {"error": "No 1m data available yet; wait for first refresh"}
    latest_price = rows[0]["price"]
    try:
        result = await asyncio.to_thread(
            place_short_order, symbol, latest_price, tp_pct, sl_pct, amount, leverage
        )
        return {
            "ok": True, "symbol": symbol, "price": latest_price,
            "tp_pct": tp_pct, "sl_pct": sl_pct, "amount": amount, "leverage": leverage,
            "response": result,
        }
    except Exception as e:
        logging.error("manual_short failed for %s: %s", symbol, e)
        return {"error": str(e)}


_instruments_cache: list | None = None
_instruments_cache_ts: float = 0.0
_INSTRUMENTS_TTL = 3600.0


@app.get("/api/instruments")
async def get_instruments():
    """Return all linear perpetual instruments from Bybit with funding rate (cached 1 h)."""
    global _instruments_cache, _instruments_cache_ts
    now = time.time()
    if _instruments_cache is None or now - _instruments_cache_ts > _INSTRUMENTS_TTL:
        try:
            raw_inst, raw_tick = await asyncio.gather(
                asyncio.to_thread(lambda: bybit_session.get_instruments_info(category="linear")),
                asyncio.to_thread(lambda: bybit_session.get_tickers(category="linear")),
            )
            funding = {t["symbol"]: t.get("fundingRate") for t in raw_tick["result"]["list"]}
            instruments = raw_inst["result"]["list"]
            for inst in instruments:
                inst["fundingRate"] = funding.get(inst["symbol"])
            _instruments_cache = instruments
            _instruments_cache_ts = now
        except Exception as e:
            logging.error("get_instruments failed: %s", e)
            if _instruments_cache is None:
                return {"error": str(e), "instruments": [], "count": 0}
    return {"instruments": _instruments_cache, "count": len(_instruments_cache)}


def _trading_symbols() -> list[str]:
    """Извлекает список Trading USDT LinearPerpetual символов из кэша инструментов."""
    if not _instruments_cache:
        return []
    return [
        i["symbol"] for i in _instruments_cache
        if i.get("quoteCoin") == "USDT"
        and i.get("contractType") == "LinearPerpetual"
        and i.get("status") == "Trading"
    ]


@app.get("/api/overbought")
async def get_overbought():
    """Вернуть текущее состояние сканирования и дефолтные пороги из конфига."""
    return {
        "state":      overbought.state,
        "updated_at": overbought.updated_at,
        "is_scanning": overbought.is_scanning,
        "defaults":   OVERBOUGHT_THRESHOLDS,
    }


@app.post("/api/overbought/scan")
async def trigger_overbought_scan():
    """Запустить сканирование RSI 1D/4H/1H/1m. Если кэш свежий — вернуть его сразу."""
    if overbought.is_cache_fresh():
        return {
            "status":     "cached",
            "state":      overbought.state,
            "updated_at": overbought.updated_at,
        }
    if overbought.is_scanning:
        return {"status": "already_scanning"}

    symbols = _trading_symbols()
    if not symbols:
        try:
            raw = await asyncio.to_thread(
                lambda: bybit_session.get_instruments_info(category="linear")
            )
            symbols = [
                i["symbol"] for i in raw["result"]["list"]
                if i.get("quoteCoin") == "USDT"
                and i.get("contractType") == "LinearPerpetual"
                and i.get("status") == "Trading"
            ]
        except Exception as e:
            return {"error": str(e)}

    asyncio.create_task(overbought.run_scan(symbols))
    return {"status": "started", "count": len(symbols)}


@app.get("/api/auto-order")
async def get_auto_order():
    """Return auto-order enabled state for every ticker."""
    return {t: (t in monitor._auto_order_tickers) for t in monitor.TABLE_TICKERS}


@app.post("/api/monitor/tickers")
async def add_monitor_tickers(symbols: list[str] = Body(...)):
    """Replace dynamic tickers in RSI monitor with the provided list."""
    result = monitor.set_dynamic_tickers(symbols)
    if result["added"] or result["removed"]:
        logging.info("Dynamic tickers updated: +%s -%s", result["added"], result["removed"])
        asyncio.create_task(monitor.refresh_tables())
    return {**result, "total": len(monitor.TABLE_TICKERS)}


@app.post("/api/auto-order/{symbol}")
async def set_auto_order(symbol: str, enabled: bool):
    """Enable or disable auto-order for a ticker."""
    if symbol not in monitor.TABLE_TICKERS:
        return {"error": f"Unknown ticker: {symbol}"}
    if enabled:
        monitor._auto_order_tickers.add(symbol)
    else:
        monitor._auto_order_tickers.discard(symbol)
    monitor._save_auto_order_state()
    logging.info("Auto-order %s: %s", symbol, "ON" if enabled else "OFF")
    return {"symbol": symbol, "enabled": symbol in monitor._auto_order_tickers}
