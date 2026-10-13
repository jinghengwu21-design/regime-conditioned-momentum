# Design references

SARKAZ combines a strategy research terminal with an auditable Agent runtime. The following projects informed its information architecture and module boundaries. Their code is not vendored into the application.

Repository and source review: 13 October 2026.

| Reference | Material reviewed | Applied in SARKAZ |
|---|---|---|
| [OpenBB Workspace](https://github.com/OpenBB-finance/workspace) | React workspace layout, [`Metric.tsx`](https://github.com/OpenBB-finance/workspace/blob/be00e95019a55d57af146919ee46b7e1a4859226/terminalpro/src/components/Widgets/Metric.tsx), theme state | Persistent navigation, consistent widget headings, stable research scope and coherent financial number formatting |
| [QuantStats](https://github.com/ranaroussi/quantstats) | [`stats.py`](https://github.com/ranaroussi/quantstats/blob/9ef4c6d0a4ffe7831f6ebba6a5824fd33a90c05a/quantstats/stats.py): monthly returns, rolling Sharpe and drawdown episodes; report template | A complete performance view: cumulative path, benchmark, underwater chart, calendar returns and recovery periods |
| [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | [Desktop architecture](https://github.com/AI4Finance-Foundation/FinRobot/blob/2717499b8e30f242640af08c4ad9afd1113c2d45/finrobot_desktop/README.md), pipeline base and narrative numeric grounding operator | Keep computation, narrative and review separate; expose the rejected draft and the tool result that corrects it |
| [TradingAgents](https://github.com/TauricResearch/TradingAgents) | README, version history and point-in-time data discussion | Treat dataset time, run time and analysis scope as separate identities; show the recorded execution time |

OpenBB Workspace was archived when reviewed. It is a design reference, not a runtime dependency. The other repositories are also references rather than claims of affiliation.

## Decisions

**Strategy before orchestration.** The first screen answers how the strategy performed and where its risk lies. Agent traces have their own workspace. A visitor can reach an individual trade directly from a monthly return cell.

**One calculation contract across surfaces.** Python builds the full research dataset. Browser cost scenarios use the same fill-notional formula and are tested against Python outputs across four periods and three fee levels.

**Two deployment surfaces.** GitHub Pages hosts the interactive research snapshot without a server or credentials. The local Python service executes the same LangGraph workflow and exposes the trace to the same React interface. A recorded trace is always labelled as recorded.

**Use financial conventions deliberately.** The benchmark is an unlevered BTC price reference, aligned to complete daily bars. Trade win rate remains trade-based; daily Sharpe remains calendar-based. An open drawdown stays unrecovered at the observation boundary.

**Restrained visual hierarchy.** Graphite surfaces, tabular numbers, muted grid lines and a small semantic palette make changes in equity, loss and scenario assumptions legible. Colour is accompanied by labels, signs and units. Fonts ship with the application.

## Boundaries of reuse

The application, calculations and UI are original project code. Open-source references are credited here; dependencies retain their own licenses in [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md). SARKAZ does not reuse their branding, screenshots, claims of adoption or research results.
