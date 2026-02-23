import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from crypt.bit import fetch_rsi_data

TABLE_TICKERS = ["HYPEUSDT", "BTCUSD"]

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "front")

table_state: dict = {ticker: [] for ticker in TABLE_TICKERS}
table_updated_at: str = "—"


async def refresh_tables():
    global table_updated_at
    for ticker in TABLE_TICKERS:
        try:
            records = await asyncio.to_thread(fetch_rsi_data, ticker)
            table_state[ticker] = [
                {
                    "time":  r["time"].strftime("%Y-%m-%d %H:%M"),
                    "price": r["price"],
                    "rsi":   round(r["rsi"], 2),
                }
                for r in records
            ]
        except Exception as e:
            print(f"Table fetch error [{ticker}]: {e}")
    table_updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def table_monitor():
    while True:
        await asyncio.sleep(60)
        await refresh_tables()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await refresh_tables()          # заполнить сразу при старте
    asyncio.create_task(table_monitor())
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(request=request, name="main.html", context={})


@app.get("/api/table")
async def table_json():
    return {"tickers": TABLE_TICKERS, "data": table_state, "updated_at": table_updated_at}