# Development Guide & Testing Conventions

## 1. Safety Architecture

The Prophecy platform defaults to `MANUAL_CONFIRMATION` or `AUTO_PAPER` modes. Real broker live trading is locked behind a strict 6-lock safety gate requiring explicit environment keys (`PROPHECY_EXECUTION_MODE=LIVE`, `PROPHECY_LIVE_TRADING_ACKNOWLEDGED=TRUE`, `PROPHECY_OPERATOR_SIGNATURE`), single-use confirmation tokens with 60s TTL, and hard order notional/quantity ceilings.

---

## 2. Test Suites Execution

Run all test suites using `uv`:

```powershell
$env:Path = "C:\Users\Middleware\.local\bin\mingit\cmd;C:\Users\Middleware\.local\bin;$env:Path"

# 1. Engine Domain & Strategy Tests (93 unit tests)
uv run python -m unittest discover -s engine/tests -v

# 2. FastAPI Backend & API Integration Tests (7 integration tests)
uv run --with fastapi --with uvicorn --with pydantic --with httpx python -m unittest discover -s backend/app/tests -v
```

---

## 3. Code Quality, Linting & Formatting

Format and lint all code with `ruff`:

```powershell
# Format code
uv run --with ruff ruff format engine/src engine/tests backend/app

# Lint code and fix issues
uv run --with ruff ruff check --fix engine/src engine/tests backend/app
```

---

## 4. Starting the Development Backend Server

```powershell
$env:Path = "C:\Users\Middleware\.local\bin\mingit\cmd;C:\Users\Middleware\.local\bin;$env:Path"
$env:PYTHONPATH = "engine/src;backend"
uv run --with fastapi --with uvicorn --with pydantic uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
