# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An early-stage Python project combining a FastAPI REST API with crypto/financial market data retrieval via the [Massive](https://massive.io) API (formerly Polygon.io).

## Running the Application

```bash
# Activate the virtual environment (Python 3.14)
source .venv/Scripts/activate   # Windows Git Bash
# or
.venv\Scripts\activate          # Windows CMD/PowerShell

# Run the FastAPI dev server
uvicorn crypto.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. FastAPI auto-generates interactive docs at `/docs`.

## Running Scripts Directly

```bash
# Fetch RSI data for X:HYPEUSD from Massive API
python crypto/cr.py

# Print current Unix timestamp (debug utility)
python crypto/otladka.py
```

## Project Structure

```
crypto/
├── main.py       # FastAPI app with HTTP endpoints
├── cr.py         # Massive API client — fetches RSI indicator data for crypto tickers
├── otladka.py    # Scratch/debug utility
└── test_main.http  # Manual HTTP tests for endpoints (JetBrains/VS Code REST Client)
```

## Architecture

- **`crypto/main.py`** — FastAPI application. All endpoints are `async def`. Currently defines `/` and `/hello/{name}`.
- **`crypto/cr.py`** — Standalone script using `massive.RESTClient` to query technical indicators (RSI) for crypto pairs. The API key is currently hardcoded here — it should be moved to an environment variable before any production use.
- No database, no authentication layer, no test framework currently configured.

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` 0.131.0 | Web framework |
| `starlette` 0.52.1 | ASGI foundation (used by FastAPI) |
| `pydantic` 2.x | Request/response validation |
| `massive` 2.2.0 | Massive (Polygon.io) REST API client for market data |
| `uvicorn` | ASGI server (must be installed separately if missing) |

## Notes

- The Massive API key in `cr.py:5` is exposed in source — use `os.environ` or a `.env` file instead.
- No `requirements.txt` or `pyproject.toml` exists yet; dependencies are only tracked by the `.venv`.
