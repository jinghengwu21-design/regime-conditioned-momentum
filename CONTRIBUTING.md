# Contributing

Start with [README](README.md), [architecture](docs/ARCHITECTURE.md) and the [data card](data/DATA_CARD.md).

1. Install the Python lock and run `npm ci` in `web/`.
2. Keep numeric conventions documented. Add a regression test for changed financial behaviour.
3. Run `python -m pytest tests`, then `npm test` and `npm run build` in `web/`.
4. For changes to exported research assets, run `python scripts/build_terminal.py` and inspect the regenerated views.
5. Keep archived strategy files byte-identical. New strategy research needs a new identity and explicit data protocol.

Report calculation issues with the dataset ID, period, fee assumptions, expected value and observed value. Never include API keys, live trading credentials or private account data in an issue.
