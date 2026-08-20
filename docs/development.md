# Development

## Safety boundary

The engine is signal/paper-trading only. Broker credentials are read only from environment variables in future adapters; they must never be committed or included in mobile code. Live execution is feature-gated and is not part of M0.

## M0 commands

```powershell
python -m unittest discover -s engine/tests -v
python -m unittest discover -s backend/app/tests -v
npm --prefix mobile test
```

## Quality tools

Each Python package carries Ruff configuration in `pyproject.toml`. Once development dependencies are installed, run `ruff check .` and `ruff format --check .` from that package directory. The mobile project reserves `lint` for the Expo lint configuration added with the first real Expo application milestone.

## Next milestone

M1 adds mocked, protocol-based Groww market-data and instrument adapters. It must not make live broker order calls.
