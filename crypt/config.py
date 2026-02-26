"""
Централизованная конфигурация мониторинга.

Чтобы добавить тикер или изменить пороги RSI для сигнала SHORT —
отредактируй словарь TICKERS ниже.
"""

from dataclasses import dataclass

# --- Bybit API credentials ---
BYBIT_API_KEY    = 'gQD1td9XGAaMU0bU4j'
BYBIT_API_SECRET = 'VYyJC1to8ZRFJMEGGZxFuo8J0fWnCDhuRsTA'


@dataclass
class ShortCriteria:
    """Пороги RSI для сигнала SHORT по каждому таймфрейму.

    price_precision — количество знаков после запятой при сравнении цен.
    Должно совпадать с точностью отображения цены для данного тикера,
    чтобы «одинаковые на экране» цены не вызывали ложных сигналов.
    """
    rsi_15m:         float = 50.0
    rsi_1h:          float = 60.0
    rsi_4h:          float = 70.0
    rsi_1d:          float = 70.0
    price_precision: int   = 5     # знаков после запятой для сравнения цен
    use_day_high:    bool  = True  # требовать превышения внутридневного максимума


@dataclass
class LongCriteria:
    """Пороги RSI для сигнала LONG по каждому таймфрейму.

    Условие на RSI: значение должно быть НИЖЕ порога (перепроданность).
    use_day_low — учитывать ли условие price < day_low_so_far.
    """
    rsi_15m:         float = 50.0
    rsi_1h:          float = 40.0
    rsi_4h:          float = 30.0
    rsi_1d:          float = 30.0
    price_precision: int   = 5
    use_day_low:     bool  = True


# Пороги RSI для сканера перекупленных монет (значения по умолчанию)
OVERBOUGHT_THRESHOLDS: dict[str, float] = {
    "rsi_1d":  85.0,
    "rsi_4h":  82.0,
    "rsi_1h":  82.0,
    "rsi_15m": 85.0,
    "rsi_1m":  92.0,
}


# Критерии SHORT по тикерам (RSI > порога + price > day_high)
TICKERS: dict[str, ShortCriteria] = {
    "HYPEUSDT":   ShortCriteria(rsi_15m=50, rsi_1h=60, rsi_4h=70, rsi_1d=70),
    "BTCUSDT":    ShortCriteria(rsi_15m=50, rsi_1h=60, rsi_4h=70, rsi_1d=70),
    "VVVUSDT":    ShortCriteria(rsi_15m=50, rsi_1h=60, rsi_4h=70, rsi_1d=70),
    "BTRUSDT":    ShortCriteria(rsi_15m=75, rsi_1h=65, rsi_4h=50, rsi_1d=62),
    "PIPPINUSDT": ShortCriteria(rsi_15m=60, rsi_1h=60, rsi_4h=60, rsi_1d=60),
    "ESPUSDT":    ShortCriteria(rsi_15m=60, rsi_1h=60, rsi_4h=50, rsi_1d=62),
    "POWERUSDT":    ShortCriteria(rsi_15m=60, rsi_1h=60, rsi_4h=50, rsi_1d=62),
}

# Критерии LONG по тикерам (RSI < порога + price < day_low)
LONG_TICKERS: dict[str, LongCriteria] = {
    "HYPEUSDT":   LongCriteria(rsi_15m=50, rsi_1h=40, rsi_4h=30, rsi_1d=30),
    "BTCUSDT":    LongCriteria(rsi_15m=50, rsi_1h=40, rsi_4h=30, rsi_1d=30),
    "VVVUSDT":    LongCriteria(rsi_15m=50, rsi_1h=40, rsi_4h=30, rsi_1d=30),
    "BTRUSDT":    LongCriteria(rsi_15m=25, rsi_1h=35, rsi_4h=50, rsi_1d=38),
    "PIPPINUSDT": LongCriteria(rsi_15m=40, rsi_1h=40, rsi_4h=40, rsi_1d=40),
    "ESPUSDT":    LongCriteria(rsi_15m=40, rsi_1h=40, rsi_4h=50, rsi_1d=38),
}