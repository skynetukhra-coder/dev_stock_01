# Production Operations Runbooks

## Runbook 1: Emergency Kill Switch Activation (Global Market Halt)

### Symptoms
- Abnormal market volatility, exchange circuit breaker trips, or broker feed instability.
- Sudden unforeseen drawdown approaching daily risk limits.

### Procedure
1. Send an emergency POST request to `/kill-switch`:
   ```bash
   curl -X POST http://localhost:8000/kill-switch \
     -H "Content-Type: application/json" \
     -d '{"active": true, "operator_id": "oncall-admin", "reason": "Emergency market halt"}'
   ```
2. Verify that `kill_switch_active` is `true` via `GET /risk/status`.
3. In this state:
   - **All new entry orders** (paper or live) are blocked immediately.
   - **Position exits and stop-loss liquidations** continue to execute freely.

---

## Runbook 2: Daily Realized Loss Breach / Risk Lockdown

### Symptoms
- Daily realized loss exceeds ₹10,000 ceiling.
- Risk manager rejects signals with `MAX_DAILY_REALIZED_LOSS_BREACHED`.

### Procedure
1. Risk Manager automatically locks the session from taking further entries.
2. Review active positions via `GET /positions`.
3. Allow active position trailing stops / profit targets to execute naturally or manually square off via broker terminal.
4. Risk state automatically resets at the beginning of the next trading day (09:15 IST).

---

## Runbook 3: Broker Disconnection / Data Feed Latency

### Symptoms
- SSE stream drops or price candles fail to arrive for > 60 seconds.
- `GET /health` indicates disconnection or stale timestamp.

### Procedure
1. Check the Groww broker gateway connection logs.
2. In the event of feed unresponsiveness, the engine safely flags `BrokerUnhealthy` and prevents signal generation.
3. Restart backend service container once upstream feed resumes.
