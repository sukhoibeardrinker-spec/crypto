import bisect
import datetime
import logging

from pybit.unified_trading import HTTP

from crypt.config import BYBIT_API_KEY, BYBIT_API_SECRET, ShortCriteria, LongCriteria

session = HTTP(
    testnet=False,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET,
)

RSI_PERIOD = 14


def calculate_rsi_series(prices: list, period: int = 14) -> list:
    """Return a list of RSI values, one per candle after the warm-up.

    The first RSI is at index `period` (uses candles 0..period inclusive).
    Returns a list of floats aligned to prices[period:].
    """
    if len(prices) < period + 1:
        raise ValueError(f"Need at least {period + 1} data points, got {len(prices)}")

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains  = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    # Seed Wilder's averages with a simple mean over the first `period` deltas
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def rsi_from_avgs(ag, al):
        if al == 0:
            return 100.0
        return 100.0 - (100.0 / (1.0 + ag / al))

    results = [rsi_from_avgs(avg_gain, avg_loss)]  # RSI at candle index `period`

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        results.append(rsi_from_avgs(avg_gain, avg_loss))

    return results


def fetch_rsi_data(symbol: str, interval: int = 1, period: int = RSI_PERIOD, limit: int = 1000):
    res = session.get_index_price_kline(
        category="linear", symbol=symbol, interval=interval, limit=limit,
    )
    candles = list(reversed(res["result"]["list"]))
    closes = [float(c[4]) for c in candles]
    rsi_values = calculate_rsi_series(closes, period)

    records = [
        {
            "time":  datetime.datetime.fromtimestamp(int(candles[period + i][0]) / 1000),
            "price": closes[period + i],
            "rsi":   rsi,
        }
        for i, rsi in enumerate(rsi_values)
    ]

    return records


def check_short_signal(row: dict, criteria: ShortCriteria) -> bool:
    """Return True when all RSI thresholds are breached.

    If criteria.use_day_high is True (default), also requires price to strictly
    exceed the running intraday high of all prior candles of the same day.
    """
    if criteria.use_day_high:
        day_high = row.get("day_high_so_far")
        if day_high is None:
            return False
        p = criteria.price_precision
        if not (round(row["price"], p) > round(day_high, p)):
            return False

    return (
        row.get("rsi_15m") is not None and row["rsi_15m"] > criteria.rsi_15m and
        row.get("rsi_1h")  is not None and row["rsi_1h"]  > criteria.rsi_1h  and
        row.get("rsi_4h")  is not None and row["rsi_4h"]  > criteria.rsi_4h  and
        row.get("rsi_1d")  is not None and row["rsi_1d"]  > criteria.rsi_1d
    )


def check_long_signal(row: dict, criteria: LongCriteria) -> bool:
    """Return True when all RSI values are below their thresholds (oversold).

    If criteria.use_day_low is True (default), also requires price to be strictly
    below the running intraday low of all prior candles of the same day.
    """
    if criteria.use_day_low:
        day_low = row.get("day_low_so_far")
        if day_low is None:
            return False
        p = criteria.price_precision
        if not (round(row["price"], p) < round(day_low, p)):
            return False

    return (
        row.get("rsi_15m") is not None and row["rsi_15m"] < criteria.rsi_15m and
        row.get("rsi_1h")  is not None and row["rsi_1h"]  < criteria.rsi_1h  and
        row.get("rsi_4h")  is not None and row["rsi_4h"]  < criteria.rsi_4h  and
        row.get("rsi_1d")  is not None and row["rsi_1d"]  < criteria.rsi_1d
    )


def fetch_rsi_multi(
    symbol: str,
    criteria: ShortCriteria | None = None,
    long_criteria: LongCriteria | None = None,
    base_interval: int = 15,
    base_limit: int = 110,
    period: int = RSI_PERIOD,
):
    """Fetch RSI for base + 1H, 4H, 1D intervals, all aligned to base candles.

    base_interval — candle size in minutes for the base timeframe (1 or 15).
    base_limit    — how many base candles to fetch.
    Returns a list (oldest → newest) of dicts:
        time, price, rsi_15m, rsi_1h, rsi_4h, rsi_1d, day_high_so_far, is_short, ...
    Higher-TF fields can be None if no matching candle is found.
    """
    if criteria is None:
        criteria = ShortCriteria()

    HT_LIMIT = 110  # candle count for higher timeframes (1H / 4H / 1D)

    def _fetch_candles(interval, lim=HT_LIMIT):
        """Return candles sorted oldest → newest."""
        res = session.get_index_price_kline(
            category="linear", symbol=symbol, interval=interval, limit=lim,
        )
        return list(reversed(res["result"]["list"]))

    def _rsi_map(candles):
        """Return {open_ts_ms: rsi} for candles that have enough history."""
        closes = [float(c[4]) for c in candles]
        rsi_values = calculate_rsi_series(closes, period)
        return {int(candles[period + i][0]): rsi for i, rsi in enumerate(rsi_values)}

    def _make_lookup(rsi_map):
        """Return ts_ms → RSI of the candle that was active at that moment."""
        sorted_keys = sorted(rsi_map.keys())

        def lookup(ts_ms):
            idx = bisect.bisect_right(sorted_keys, ts_ms) - 1
            return rsi_map[sorted_keys[idx]] if idx >= 0 else None

        return lookup

    # --- fetch raw candles ---
    candles_base = _fetch_candles(base_interval, lim=base_limit)
    candles_1h   = _fetch_candles(60)
    candles_4h   = _fetch_candles(240)
    candles_1d   = _fetch_candles("D")

    # --- RSI lookups for higher timeframes ---
    lookup_1h = _make_lookup(_rsi_map(candles_1h))
    lookup_4h = _make_lookup(_rsi_map(candles_4h))
    lookup_1d = _make_lookup(_rsi_map(candles_1d))

    # --- base RSI ---
    closes_base = [float(c[4]) for c in candles_base]
    rsi_base    = calculate_rsi_series(closes_base, period)

    # First pass: build records without day_high_so_far
    result = []
    for i, rsi in enumerate(rsi_base):
        ts_ms = int(candles_base[period + i][0])
        result.append({
            "time":    datetime.datetime.fromtimestamp(ts_ms / 1000),
            "price":   closes_base[period + i],
            "rsi_15m": rsi,            # key stays rsi_15m regardless of base interval
            "rsi_1h":  lookup_1h(ts_ms),
            "rsi_4h":  lookup_4h(ts_ms),
            "rsi_1d":  lookup_1d(ts_ms),
        })

    # Second pass: running intraday high/low and signals (oldest → newest)
    day_running_max: dict = {}
    day_running_min: dict = {}
    for rec in result:
        d = rec["time"].date()
        rec["day_high_so_far"] = day_running_max.get(d)
        rec["day_low_so_far"]  = day_running_min.get(d)
        prev_max = day_running_max.get(d)
        prev_min = day_running_min.get(d)
        day_running_max[d] = rec["price"] if prev_max is None else max(prev_max, rec["price"])
        day_running_min[d] = rec["price"] if prev_min is None else min(prev_min, rec["price"])
        rec["is_short"] = check_short_signal(rec, criteria)
        rec["is_long"]  = check_long_signal(rec, long_criteria) if long_criteria else False

    # Third pass: profit metrics
    current_price = result[-1]["price"] if result else None

    for i, rec in enumerate(result):
        signal_price = rec["price"]
        prices_after = [r["price"] for r in result[i + 1:]]

        # SHORT: profit when price falls
        if rec["is_short"] and current_price is not None:
            rec["potential_profit_pct"] = round(
                (signal_price - min(prices_after)) / signal_price * 100, 2
            ) if prices_after else None
            rec["current_profit_pct"] = round(
                (signal_price - current_price) / signal_price * 100, 2
            )
        else:
            rec["potential_profit_pct"] = None
            rec["current_profit_pct"]   = None

        # LONG: profit when price rises
        if rec["is_long"] and current_price is not None:
            rec["long_potential_profit_pct"] = round(
                (max(prices_after) - signal_price) / signal_price * 100, 2
            ) if prices_after else None
            rec["long_current_profit_pct"] = round(
                (current_price - signal_price) / signal_price * 100, 2
            )
        else:
            rec["long_potential_profit_pct"] = None
            rec["long_current_profit_pct"]   = None

    return result
