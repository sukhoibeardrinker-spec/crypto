import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from crypt.bit import fetch_rsi_multi
from crypt.config import TICKERS

TABLE_TICKERS = list(TICKERS.keys())

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "front")

table_state: dict = {ticker: [] for ticker in TABLE_TICKERS}
detail_state: dict = {ticker: [] for ticker in TABLE_TICKERS}
table_updated_at: str = "—"


def _fmt_multi(r: dict) -> dict:
    return {
        "time":           r["time"].strftime("%Y-%m-%d %H:%M"),
        "price":          r["price"],
        "rsi_15m":        round(r["rsi_15m"], 2),
        "rsi_1h":         round(r["rsi_1h"], 2) if r["rsi_1h"] is not None else None,
        "rsi_4h":         round(r["rsi_4h"], 2) if r["rsi_4h"] is not None else None,
        "rsi_1d":         round(r["rsi_1d"], 2) if r["rsi_1d"] is not None else None,
        "day_high_so_far": round(r["day_high_so_far"], 2) if r["day_high_so_far"] is not None else None,
        "is_short":        r["is_short"],
    }


async def refresh_tables():
    global table_updated_at
    for ticker in TABLE_TICKERS:
        try:
            records = await asyncio.to_thread(fetch_rsi_multi, ticker, TICKERS[ticker])

            # overview cache (15m RSI only, oldest → newest)
            table_state[ticker] = [
                {
                    "time":  r["time"].strftime("%Y-%m-%d %H:%M"),
                    "price": r["price"],
                    "rsi":   round(r["rsi_15m"], 2),
                }
                for r in records
            ]

            # detail cache (all timeframes, newest → oldest)
            detail_state[ticker] = [_fmt_multi(r) for r in reversed(records)]

        except Exception as e:
            print(f"Table fetch error [{ticker}]: {e}")
    table_updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def table_monitor():
    while True:
        await asyncio.sleep(60)
        await refresh_tables()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await refresh_tables()
    asyncio.create_task(table_monitor())
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(request=request, name="main.html", context={})


@app.get("/api/table")
async def table_json():
    return {"tickers": TABLE_TICKERS, "data": table_state, "updated_at": table_updated_at}


@app.get("/api/ticker/{symbol}")
async def ticker_detail(symbol: str):
    if symbol not in TABLE_TICKERS:
        return {"error": f"Unknown ticker: {symbol}"}
    return {
        "ticker":     symbol,
        "data":       detail_state.get(symbol, []),
        "updated_at": table_updated_at,
    }
