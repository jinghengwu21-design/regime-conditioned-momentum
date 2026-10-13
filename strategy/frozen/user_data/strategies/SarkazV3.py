from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

import pandas as pd


STRATEGY_DIR = Path(__file__).resolve().parent
if str(STRATEGY_DIR) not in sys.path:
    sys.path.insert(0, str(STRATEGY_DIR))

from SarkazAddonProbes import SarkazWGLaunchAdd25Close1ROriginalBEV1  # noqa: E402


class SarkazV3(SarkazWGLaunchAdd25Close1ROriginalBEV1):
    """
    Stable BTC perpetual wrapper for Sarkaz V3.

    This is a naming/runtime wrapper around the frozen
    `SarkazWGLaunchAdd25Close1ROriginalBEV1` candidate. It intentionally does
    not change entries, sizing, add-on rules, stops, trailing, or exits.
    """

    VERSION_LABEL = "Sarkaz V3"
    SUPPORTED_PAIRS = {"BTC/USDT:USDT"}
    ENTER_TAG_BASE = "sarkaz_v3_low_v1"
    ENTER_TAG_HIGH = "sarkaz_v3_high_v1"

    def _analyzed_dataframe(self, pair: str) -> pd.DataFrame | None:
        if not self.dp:
            return None
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        except Exception:
            return None
        if dataframe is None or dataframe.empty or "date" not in dataframe:
            return None

        last_row = dataframe.iloc[-1]
        fingerprint = (
            len(dataframe),
            str(last_row.get("date")),
            str(last_row.get("open")),
            str(last_row.get("high")),
            str(last_row.get("low")),
            str(last_row.get("close")),
            str(last_row.get("volume")),
        )
        cache: dict[str, tuple[tuple[int, str, str, str, str, str, str], pd.DataFrame]] = getattr(
            self, "_sarkaz_v3_analyzed_cache", {}
        )
        cached = cache.get(pair)
        if cached is not None and cached[0] == fingerprint:
            return cached[1]

        normalized = dataframe.copy()
        normalized["date"] = pd.to_datetime(normalized["date"], utc=True)
        if not normalized["date"].is_monotonic_increasing:
            normalized = normalized.sort_values("date").reset_index(drop=True)

        cache[pair] = (fingerprint, normalized)
        self._sarkaz_v3_analyzed_cache = cache
        return normalized

    def _row_before(
        self, dataframe: pd.DataFrame, when: datetime | pd.Timestamp
    ) -> pd.Series | None:
        if dataframe.empty or "date" not in dataframe:
            return None
        ts = self._utc(when)
        try:
            idx = int(dataframe["date"].searchsorted(ts, side="left")) - 1
        except TypeError:
            dates = pd.to_datetime(dataframe["date"], utc=True)
            idx = int(dates.searchsorted(ts, side="left")) - 1
        if idx < 0:
            return None
        return dataframe.iloc[idx]
