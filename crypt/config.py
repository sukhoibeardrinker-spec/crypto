"""
Централизованная конфигурация мониторинга.

Чтобы добавить тикер или изменить пороги RSI для сигнала SHORT —
отредактируй словарь TICKERS ниже.
"""

from dataclasses import dataclass

# --- Bybit API credentials ---
BYBIT_API_KEY    = '799hm9EMCGgvjaFOIn'
BYBIT_API_SECRET = 'KASq8mgoSFnBPXHLd4ZfWV8vPXzBxweDim6y'


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


# Ключ — символ тикера (Bybit linear), значение — критерии SHORT-сигнала.
# Порядок определяет порядок кнопок на фронтенде.
TICKERS: dict[str, ShortCriteria] = {
    "HYPEUSDT":   ShortCriteria(rsi_15m=50, rsi_1h=60, rsi_4h=70, rsi_1d=70),
    "BTCUSDT":    ShortCriteria(rsi_15m=50, rsi_1h=60, rsi_4h=70, rsi_1d=70),
    "VVVUSDT":    ShortCriteria(rsi_15m=50, rsi_1h=60, rsi_4h=70, rsi_1d=70),
    "BTRUSDT":    ShortCriteria(rsi_15m=50, rsi_1h=60, rsi_4h=70, rsi_1d=70),
    "PIPPINUSDT": ShortCriteria(rsi_15m=50, rsi_1h=60, rsi_4h=70, rsi_1d=70),
}