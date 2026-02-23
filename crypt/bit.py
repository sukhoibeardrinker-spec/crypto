
from pybit.unified_trading import HTTP

key = '799hm9EMCGgvjaFOIn'
secret_key = 'KASq8mgoSFnBPXHLd4ZfWV8vPXzBxweDim6y'

session = HTTP(
    testnet=True,
    api_key=key,
    api_secret=secret_key,
)

RSI_PERIOD = 14
SYMBOL = "BTCUSDT"


import datetime


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


def fetch_rsi_data(symbol: str, interval: int = 15, period: int = RSI_PERIOD, limit: int = 110):
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


if __name__ == "__main__":
    records = fetch_rsi_data(SYMBOL)

    print(f"{'Timestamp':<20} {'Price':>12} {'RSI-14':>8}")
    print("-" * 44)
    for r in records:
        print(f"{r['time'].strftime('%Y-%m-%d %H:%M'):<20} {r['price']:>12.2f} {r['rsi']:>8.2f}")

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"Latest RSI-{RSI_PERIOD}: {records[-1]['rsi']:.2f}")

