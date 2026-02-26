"""
Фоновое сканирование RSI 1D / 4H / 1H / 1m по всем Trading USDT-LinearPerpetual.

Ускорения:
 - Выделенный ThreadPoolExecutor (60 потоков) — не конкурирует с основным пулом.
 - Все 4 интервала на символ запрашиваются параллельно.
 - Семафор ограничивает число одновременных HTTP-запросов (не символов).
 - Кэш 5 минут — повторный запуск в течение TTL возвращает готовые данные.
"""
import asyncio
import concurrent.futures
import logging
import time
from datetime import datetime

from crypt.bit import session, calculate_rsi_series

RSI_PERIOD   = 14
_CACHE_TTL   = 300.0   # 5 минут
_POOL_SIZE   = 60      # потоков в выделенном пуле
_SEM_SIZE    = 30      # макс. параллельных HTTP-запросов

_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=_POOL_SIZE, thread_name_prefix="ob"
)

# ── публичное состояние ────────────────────────────────────────────
state:       dict[str, dict] = {}
updated_at:  str  = ""
is_scanning: bool = False
_cache_ts:   float = 0.0


def is_cache_fresh() -> bool:
    return bool(state) and (time.time() - _cache_ts < _CACHE_TTL)


def _last_rsi(symbol: str, interval) -> float | None:
    """Синхронный fetch RSI-14 последней свечи (выполняется в потоке)."""
    try:
        res = session.get_index_price_kline(
            category="linear", symbol=symbol,
            interval=interval, limit=RSI_PERIOD + 5,
        )
        candles = list(reversed(res["result"]["list"]))
        if len(candles) < RSI_PERIOD + 1:
            return None
        closes = [float(c[4]) for c in candles]
        vals = calculate_rsi_series(closes, RSI_PERIOD)
        return round(vals[-1], 2) if vals else None
    except Exception as e:
        logging.debug("ob._last_rsi %s %s: %s", symbol, interval, e)
        return None


async def run_scan(symbols: list[str]) -> None:
    """Параллельно сканирует все символы и обновляет state."""
    global state, updated_at, is_scanning, _cache_ts
    if is_scanning:
        return
    is_scanning = True

    sem  = asyncio.Semaphore(_SEM_SIZE)
    loop = asyncio.get_running_loop()

    async def _fetch(sym: str, interval):
        async with sem:
            return await loop.run_in_executor(_executor, _last_rsi, sym, interval)

    async def _one(sym: str):
        # все 5 интервалов — параллельно
        rsi_1d, rsi_4h, rsi_1h, rsi_15m, rsi_1m = await asyncio.gather(
            _fetch(sym, "D"),
            _fetch(sym, 240),
            _fetch(sym, 60),
            _fetch(sym, 15),
            _fetch(sym, 1),
        )
        return sym, rsi_1d, rsi_4h, rsi_1h, rsi_15m, rsi_1m

    try:
        results = await asyncio.gather(
            *[_one(s) for s in symbols], return_exceptions=True
        )
        new: dict[str, dict] = {}
        for r in results:
            if isinstance(r, Exception):
                continue
            sym, rsi_1d, rsi_4h, rsi_1h, rsi_15m, rsi_1m = r
            new[sym] = {
                "rsi_1d":  rsi_1d,
                "rsi_4h":  rsi_4h,
                "rsi_1h":  rsi_1h,
                "rsi_15m": rsi_15m,
                "rsi_1m":  rsi_1m,
            }
        state     = new
        _cache_ts = time.time()
        updated_at = datetime.now().strftime("%H:%M:%S %d.%m.%Y")
        logging.info("overbought scan done: %d symbols", len(state))
    finally:
        is_scanning = False
