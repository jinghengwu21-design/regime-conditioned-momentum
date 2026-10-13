# Frozen strategy source

`frozen/` preserves the source dependency set recorded for the Sarkaz V3F historical run. [manifest.json](manifest.json) maps each source file to its original SHA-256. The snapshot is byte-identical to the research archive; it retains the original directory layout, experimental base classes and historical research paths.

Start with [`SarkazV3F.py`](frozen/user_data/strategies/SarkazV3F.py), then follow `SarkazV3`, OriginalBE, the finite weight table and the base signal implementation. The readable system description is in [STRATEGY.md](../docs/STRATEGY.md).

The source snapshot runs in a Freqtrade research environment with its original market-data inputs. It is not imported by the terminal. The terminal's fully bundled reproduction path starts from `data/trades.csv`, `data/fills.csv` and `data/market_daily.csv`.

Verify source identity:

```bash
python scripts/verify_strategy.py
```
