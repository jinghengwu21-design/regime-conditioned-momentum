# Sarkaz V3F

Sarkaz V3F is a frozen BTC perpetual momentum strategy on 5-minute bars. It is long-only. A continuous native Freqtrade account provides the research ledger: 922 trades and 2,247 entry, add and exit fills.

## Trading hypothesis

Large directional candles accompanied by unusual range and participation can indicate a breakout that persists beyond the trigger bar. The system requires a compatible market regime and a completed confirmation candle before taking exposure. Position sizing and exit rules express the risk of that same signal.

| Stage | Rule | Source |
|---|---|---|
| Trigger | Signal K body share at least 0.70; rolling range filter at the 0.90 quantile; extreme-volume threshold 4.0 | `BtcNextCloseBayesLongV1Strategy.populate_indicators` |
| Regime and structure | Accept selected uptrend/upper-value regimes, then apply structure candidates | Base strategy and `market_regime` |
| Confirmation | Confirm using the next completed candle; fill at the next available native execution point | Base strategy and `SarkazFollowthroughProbes` |
| Exposure | Finite relative weight table; V3F multiplies the inherited leverage budget by 1.50, capped by the exchange limit | `SarkazCompositeProbes`, `SarkazV3F.leverage` |
| Add | One add after a completed candle closes at or above entry + 1R | `SarkazWGLaunchAdd25Close1RV1` |
| Exit | Signal-low initial stop; original-entry breakeven reference; prior four-hour-low trail; maximum 24-hour holding period | OriginalBE class and Trail4h base |

Here R is the initial absolute price risk. Native execution confirms before entering, so the next candle's closing price is not available at that candle's open.

## Source identity

The [frozen source tree](../strategy/frozen/) contains the 19 files registered in the original run protocol. Every byte matches the archived source SHA-256 recorded in [strategy/manifest.json](../strategy/manifest.json). Its combined research fingerprint is:

```text
a81d363128dea6d548be03e3da217a8f67e2f49060c2844c05c05ee54f0728f8
```

The inheritance chain is retained so that the result can be inspected against the actual research implementation. The terminal is independent of that execution engine: `research_agent/analytics.py` reconstructs analysis from the frozen ledger, while `research_agent/audit.py` independently verifies the account metrics and fill costs.

## Research observations

The archived full period produces CAGR 53.21%, daily account Sharpe 1.245 and maximum realized drawdown 30.09%. Trade win rate is 25.16%, with an average winning-to-losing-trade amount ratio of approximately 4.19. This makes payoff asymmetry and contribution concentration central research questions.

At 8 bps per side, fixed-path terminal equity declines from 17,815.79 to 11,034.63 USDT. The comparison adjusts every fill's notional cost; it does not resize trades after equity changes.

2026 through the archive boundary contributes approximately 0.55% account return. The terminal makes that period directly selectable so that full-period performance does not hide the recent plateau.

## Sample interpretation

The continuous account starts with 1,000 USDT on the 2020 calendar boundary and does not reset across years. Native effective scoring runs from 2020-01-04 11:20 to 2026-10-03 12:00 UTC. The export boundary is 12:05, exclusive.

2024 onward includes development observations. The full history is a historical research replay, rather than a wholly out-of-sample experiment. The 2020–2023 prefix matches 510 native trades in the earlier archive. Attribution by exit type or add participation is descriptive; it is not a causal ablation.

Maximum drawdown is measured on closed-trade equity. Fees are 5 bps per side and funding is excluded. Raw 5-minute market history and live account configurations are outside this repository; the bundled ledger and daily market attachment reproduce the terminal's analytics.
