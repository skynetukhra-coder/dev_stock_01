# Production Deployment Guide

## 1. Environment & Prerequisites

- **Python**: 3.9+ with `uv` package manager.
- **FastAPI / Uvicorn**: High-performance ASGI web server.
- **Containerization**: Docker & Docker Compose.
- **Reverse Proxy**: NGINX with TLS 1.3 encryption and SSE buffer bypass (`proxy_buffering off;`).

---

## 2. Docker Deployment

### Dockerfile (`infra/docker/Dockerfile`)
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi uvicorn pydantic

COPY engine /app/engine
COPY backend /app/backend
ENV PYTHONPATH="/app/engine/src:/app/backend"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 3. Environment Variables Configuration

Copy `.env.example` to `.env` and configure appropriate variables:

```ini
# Execution Mode (SIGNAL_ONLY, MANUAL_CONFIRMATION, AUTO_PAPER, LIVE)
PROPHECY_EXECUTION_MODE=MANUAL_CONFIRMATION
PROPHECY_LIVE_TRADING_ACKNOWLEDGED=FALSE
PROPHECY_OPERATOR_SIGNATURE=

# Risk Policies
PROPHECY_MAX_DAILY_REALIZED_LOSS=10000.0
PROPHECY_MAX_DAILY_TOTAL_LOSS=15000.0
PROPHECY_MAX_OPEN_POSITIONS=3
PROPHECY_MAX_TRADE_NOTIONAL=50000.0
```
