import logging

from crypt.bit import session

DEFAULT_NOTIONAL = 100.0
DEFAULT_LEVERAGE = 1
TP_PCT           = 0.02    # 2 % take-profit for short (price falls)
SL_PCT           = 0.10    # 10 % stop-loss for short (price rises)


def _calc_qty(price: float, notional: float) -> str:
    """Return qty string so that qty * price ≈ notional (±10 %)."""
    raw = notional / price
    for decimals in range(5):          # try 0, 1, 2, 3, 4 decimal places
        q = round(raw, decimals)
        if 0.9 * notional <= q * price <= 1.1 * notional:
            return str(q)
    return str(round(raw, 4))          # fallback


def place_short_order(
    symbol: str,
    signal_price: float,
    tp_pct: float   = TP_PCT,
    sl_pct: float   = SL_PCT,
    notional: float = DEFAULT_NOTIONAL,
    leverage: int   = DEFAULT_LEVERAGE,
) -> dict:
    """Place a SHORT Limit order.

    Parameters
    ----------
    symbol       : Bybit linear symbol, e.g. "BTRUSDT"
    signal_price : entry price (candle close or latest tick)
    tp_pct       : take-profit as a fraction  (0.02 = 2 %)
    sl_pct       : stop-loss as a fraction    (0.10 = 10 %)
    notional     : order size in USDT (default 100)
    leverage     : futures leverage (default 1×)
    """
    qty         = _calc_qty(signal_price, notional)
    take_profit = round(signal_price * (1 - tp_pct), 6)
    stop_loss   = round(signal_price * (1 + sl_pct), 6)

    # Set leverage before placing the order
    try:
        session.set_leverage(
            category="linear",
            symbol=symbol,
            buyLeverage=str(leverage),
            sellLeverage=str(leverage),
        )
    except Exception as e:
        # "leverage not modified" is a benign error if it's already set correctly
        logging.debug("set_leverage %s x%s: %s", symbol, leverage, e)

    logging.info(
        "Placing SHORT order: %s  price=%.6f  qty=%s  notional=%.2f  lev=%s×  TP=%.6f  SL=%.6f",
        symbol, signal_price, qty, notional, leverage, take_profit, stop_loss,
    )

    result = session.place_order(
        category="linear",
        symbol=symbol,
        isLeverage=1,
        side="Sell",
        orderType="Limit",
        orderFilter="Order",
        price=str(signal_price),
        qty=qty,
        takeProfit=str(take_profit),
        stopLoss=str(stop_loss),
    )

    logging.info("place_order response: %s", result)
    return result
