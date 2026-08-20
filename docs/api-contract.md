# Prophecy Codex API Contract

The Prophecy Backend exposes a RESTful API and Server-Sent Events (SSE) stream for operator oversight, position management, backtesting, and automated risk control.

---

## Base URL & Headers
- **Base URL**: `http://localhost:8000`
- **Content-Type**: `application/json`
- **Streaming Content-Type**: `text/event-stream`

---

## 1. System Health & Status

### `GET /health`
Returns system status, operating execution mode, live market session flag, and kill switch status.

**Response `200 OK`**:
```json
{
  "status": "ok",
  "service": "prophecy-backend",
  "timestamp": "2026-08-20T10:00:00+05:30",
  "mode": "MANUAL_CONFIRMATION",
  "is_market_open": true,
  "kill_switch_active": false
}
```

---

## 2. Signals & Operator Confirmation

### `GET /signals`
Returns all active, pending, and historical strategy signals.

**Response `200 OK`**:
```json
{
  "total": 1,
  "signals": [
    {
      "id": "sig-88421b-1",
      "symbol": "NIFTY",
      "case_number": 3,
      "created_at": "2026-08-20T10:00:00+05:30",
      "status": "PENDING_CONFIRMATION",
      "signal_type": "CALL",
      "underlying_price": 24000.0,
      "pcr": 0.75,
      "strategy_version": "0.1.0",
      "reason": "Bullish Momentum Case 3",
      "indicators": {}
    }
  ]
}
```

### `POST /signals/{signal_id}/confirm`
Manual confirmation: generates a single-use authorization token and routes orders to the execution engine.

**Request**:
```json
{
  "operator_id": "operator-01"
}
```

**Response `200 OK`**:
```json
{
  "status": "ROUTED",
  "signal_id": "sig-88421b-1",
  "message": "Successfully routed 1 order(s)",
  "orders_count": 1
}
```

### `POST /signals/{signal_id}/ignore`
Manual ignore / reject: transitions signal state to `IGNORED`.

**Request**:
```json
{
  "operator_id": "operator-01",
  "reason": "Operator rejected due to major economic news event"
}
```

**Response `200 OK`**:
```json
{
  "status": "IGNORED",
  "signal_id": "sig-88421b-1",
  "reason": "Operator rejected due to major economic news event"
}
```

---

## 3. Orders, Positions & Ledger

### `GET /orders`
Lists all filled, open, and rejected orders.

### `GET /positions`
Returns open positions with real-time mark-to-market valuations and P&L.

**Response `200 OK`**:
```json
[
  {
    "groww_symbol": "NSE-NIFTY-2026-08-27-24000-CE",
    "quantity": 25,
    "average_price": 100.0,
    "ltp": 105.0,
    "pnl": 125.0,
    "realized_pnl": 0.0,
    "unrealized_pnl": 125.0
  }
]
```

### `GET /account/summary`
Returns account ledger (initial cash, cash balance, total portfolio value, and realized/unrealized P&L).

---

## 4. Risk Controls & Emergency Kill Switch

### `GET /risk/status`
Returns real-time risk limit utilization, realized/unrealized daily P&L, and open position counts.

### `POST /kill-switch`
Emergency halt toggle. When active, all new entry orders are immediately blocked.

**Request**:
```json
{
  "active": true,
  "operator_id": "admin",
  "reason": "Emergency halt triggered by operator"
}
```

---

## 5. Backtesting Simulation

### `POST /backtest`
Simulates strategy cases across multi-timeframe candle datasets and returns comprehensive performance metrics and Markdown report.

**Request**:
```json
{
  "symbol": "NIFTY",
  "initial_capital": 100000.0,
  "stop_loss_pct": 0.20,
  "take_profit_pct": 0.40,
  "slippage_pct": 0.001
}
```

---

## 6. Real-Time Streaming (SSE)

### `GET /stream/events`
Server-Sent Events endpoint streaming live events:
- `connection`: Client connect handshake
- `signal`: New strategy signal generated
- `signal_confirmed`: Signal confirmed by operator
- `signal_ignored`: Signal rejected by operator
- `kill_switch`: Kill switch toggle update
- `order_fill`: Order execution fill event
- `risk_alert`: Risk threshold breach notification
