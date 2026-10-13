from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DatasetError(ValueError):
    pass


class DataStore:
    def __init__(self, directory: Path | str | None = None, verify: bool = True):
        self.directory = Path(directory or ROOT / "data").resolve()
        self.manifest = json.loads((self.directory / "manifest.json").read_text(encoding="utf-8"))
        if verify:
            for name, metadata in self.manifest["files"].items():
                path = (self.directory / name).resolve()
                if path.parent != self.directory or not path.is_file() or file_hash(path) != metadata["sha256"]:
                    raise DatasetError(f"数据完整性验证失败：{name}")
        self.trades = pd.read_csv(self.directory / "trades.csv")
        for col in ("open_date", "close_date"):
            self.trades[col] = pd.to_datetime(self.trades[col], utc=True)
        self.market = pd.read_csv(self.directory / "market_daily.csv")
        self.market["date"] = pd.to_datetime(self.market.date, utc=True)
        if self.trades.trade_id.duplicated().any() or self.market.date.duplicated().any():
            raise DatasetError("源数据时间或交易编号重复")
        self.trades = self.trades.sort_values(["close_date", "open_date", "trade_id"]).reset_index(drop=True)
        self.evidence = json.loads((ROOT / "references/evidence.json").read_text(encoding="utf-8"))

    def window(self, start: str, end: str) -> tuple[pd.Timestamp, pd.Timestamp]:
        left = max(pd.Timestamp(start), pd.Timestamp(self.manifest["start"]))
        right = min(pd.Timestamp(end), pd.Timestamp(self.manifest["end_exclusive"]))
        if left >= right:
            raise DatasetError("所选区间没有回测数据；请选择数据覆盖范围内的日期。")
        return left, right

    def evidence_rows(self) -> list[dict]:
        rows = []
        for item in self.evidence:
            row = dict(item)
            row["source_hash"] = self.manifest["original_report"]["sha256"] if row["id"] == "E-BACKTEST" else hashlib.sha256(row["text"].encode()).hexdigest()
            rows.append(row)
        return rows

