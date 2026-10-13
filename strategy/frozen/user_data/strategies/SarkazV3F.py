from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Any


STRATEGY_DIR = Path(__file__).resolve().parent
if str(STRATEGY_DIR) not in sys.path:
    sys.path.insert(0, str(STRATEGY_DIR))

from SarkazV3 import SarkazV3  # noqa: E402


class SarkazV3F(SarkazV3):
    """
    Frozen aggressive-risk Sarkaz V3 variant.

    This keeps the complete Sarkaz V3 trade system unchanged:
    entries, Signal-K definition, finite weight table, initial stop, +1R add,
    OriginalBE reference, prior-low trailing, and 24h max hold all remain the
    same. The only change is a uniform leverage multiplier that expresses the
    existing V3 relative weights with a larger portfolio risk budget.
    """

    VERSION_LABEL = "Sarkaz V3F"
    ENTER_TAG_BASE = "sarkaz_v3f_low_v1"
    ENTER_TAG_HIGH = "sarkaz_v3f_high_v1"
    RISK_BUDGET_LEVERAGE_MULT = 1.50

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        base_leverage = super().leverage(
            pair,
            current_time,
            current_rate,
            proposed_leverage,
            max_leverage,
            entry_tag,
            side,
            **kwargs,
        )
        return float(min(float(base_leverage) * self.RISK_BUDGET_LEVERAGE_MULT, float(max_leverage)))
