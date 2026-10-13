from __future__ import annotations

from pathlib import Path
import sys


STRATEGY_DIR = Path(__file__).resolve().parent
if str(STRATEGY_DIR) not in sys.path:
    sys.path.insert(0, str(STRATEGY_DIR))

from BtcNextCloseBayesLongV1Strategy import BtcNextCloseBayesLongV1Strategy  # noqa: E402


class BtcNextCloseBayesLongTrail4hV1Strategy(BtcNextCloseBayesLongV1Strategy):
    """
    Research-only native Freqtrade support check for the frozen Trail4h candidate.

    This inherits the frozen BTC V1 native core and changes only the structural
    trail lookback after +1R from prior 2h low to prior 4h low.

    It still does not implement the outcome-dependent Bayesian trade/pass layer.
    """

    TRAIL_2H_LOOKBACK_BARS = 48
