from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


STRATEGY_DIR = Path(__file__).resolve().parent
if str(STRATEGY_DIR) not in sys.path:
    sys.path.insert(0, str(STRATEGY_DIR))

from BtcNextCloseBayesLongTrail4hV1Strategy import BtcNextCloseBayesLongTrail4hV1Strategy  # noqa: E402


class Sarkaz(BtcNextCloseBayesLongTrail4hV1Strategy):
    """
    Aggressive dry-run candidate based on the best native Trail4h performer.

    This version intentionally removes the defensive Sarkaz V1 risk layer:
    - no dynamic Bayes entry gate,
    - no fractional stake reserve,
    - no position adjustment/adds.

    It keeps the best-performing Freqtrade-native core:
    Signal K + regime/structure + extreme volume, next-candle confirmation,
    signal-low stop, +1R breakeven, prior-4h-low trail, 24h max hold.
    """

    position_adjustment_enable = False
    max_entry_position_adjustment = -1

    ENTER_TAG = "sarkaz_trail4h_core_v2"

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = None
        if "native_entry_confirm" not in dataframe:
            return dataframe
        mask = dataframe["native_entry_confirm"].fillna(False).astype(bool)
        dataframe.loc[mask, "enter_long"] = 1
        dataframe.loc[mask, "enter_tag"] = self.ENTER_TAG
        return dataframe
