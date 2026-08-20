# Prophecy Trading Platform

Prophecy is a signal-first, paper-trading platform for validated multi-timeframe options strategies. Live broker execution is intentionally disabled.

## Repository layout

- `engine/` — strategy, market-data and paper-trading domain components.
- `backend/` — FastAPI service and persistence boundary.
- `mobile/` — Expo/React Native application placeholder.
- `docs/` — product, API and operational documentation.
- `infra/` — deployment and monitoring placeholders.

## Milestone status

M0 (repository bootstrap) is complete. The implementation currently contains only safe domain placeholders; it does not fetch market data or place broker orders.

## Prerequisites

- Python 3.9+
- Node.js LTS and npm

## Verify the bootstrap

```powershell
python -m unittest discover -s engine/tests -v
python -m unittest discover -s backend/app/tests -v
npm --prefix mobile test
```

See `docs/development.md` for conventions and next milestones.
