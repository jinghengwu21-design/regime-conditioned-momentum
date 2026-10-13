# System architecture

RCM combines a research archive, the retained strategy and trade data, a deterministic analysis engine with an Agent runtime, and a React research site.

## Research archive

`research/INTRO.md` connects the development stages. `chronicle.json` contains 48 curated decision nodes with questions, methods, observations, decisions and original source paths. `build_research.py` publishes individual notes, the full research history, CSV and browser data. The source catalog records the historical document inventory. Search, family/status filters, paired comparison and deep links operate locally in the browser.

## Research data

`DataStore` loads the bundled trade ledger, fill ledger and daily market attachment. The manifest records original source paths, file sizes, market coverage, strategy name and cost conventions. Loading checks that required files are available and rejects duplicate trade IDs or market dates. Export scripts use explicit field allowlists; live account configuration is not a dataset input.

`metrics.py` calculates account equity, realized drawdown, daily Sharpe and fill-notional costs. `analytics.py` adds calendar compounding, matched-window BTC reference returns, drawdown episodes, rolling Sharpe and exit attribution. UTC boundaries are shared with the core engine.

## Agent runtime

`workflow.py` implements a LangGraph state machine:

```text
plan → context → analysis → review → export
                              ↓       ↑
                            repair → review
```

A request freezes the asset, date interval and cost assumptions. The context node labels external material and records its screening result. Analysis uses either a fixed deterministic research workflow or a bounded model tool loop. The review node independently recalculates from CSV. A rejected narrative is retained before replacement and re-review; inconsistent engine output stops export.

| Tool | Contract |
|---|---|
| `read_market` | Fixed asset and time range; full-day coverage and gaps |
| `read_backtest` | Frozen backtest identity and account conventions |
| `calculate_metrics` | Fee and slippage must equal the request |
| `compare_costs` | Defined scenario comparison over the same scope |
| `search_evidence` | Bounded lexical retrieval from curated evidence |
| `read_evidence` | Registered evidence ID only |

Each event records its node, action, typed input, output, status, elapsed time, UTC timestamp. The report binds each Claim to its metric name, unit and evidence ID.

The OpenAI adapter uses Responses function calling and a strict Draft schema. It caps the loop at eight model rounds and twelve tool calls, uses a fixed official endpoint and `store=False`, and does not replace a failed model call with an unlabelled deterministic run.

## Browser application

`web/src/App.tsx` owns navigation and shared research scope; `web/src/pages/` separates the eight research workspaces. `components/ui.tsx` provides panels, metrics and accessible dialogs. `Chart.tsx` wraps modular ECharts with SVG rendering and resize observation. `finance.ts` implements interactive fixed-path cost attribution and trade filters. Node tests reconcile browser results with Python across the exported periods.

`build_research.py` exports the research archive. `build_terminal.py` generates `web/public/data/terminal.json`, recorded experiments and report assets. These files are the public site's only data inputs. Charts, tables and downloads work on static hosting. Model credentials never enter the frontend.

## Local API

`server.py` serves `web/dist` and two endpoints:

- `GET /api/status`: service identity and a boolean indicating model configuration.
- `POST /api/research`: a validated `ResearchRequest`, returning a research result and trace.

The default listener is loopback. Requests require JSON, have a body-size bound, reject a foreign Origin and share a two-run concurrency limit. Runtime artifacts are written under ignored `outputs/api-runs/`. The server does not accept arbitrary paths or commands.

GitHub Pages provides no Python API. The terminal shows archived records there and exposes execution controls only when the local research service is connected.

## Reproduction and tests

Python tests cover numeric identities, source windows, fill costs, report injection, external-text screening, SDK tool loops and a real ephemeral HTTP server. Frontend tests cover fee/slippage reconciliation, combined filters and CSV export. Browser checks cover the interactive paths and responsive breakpoints.

The original strategy snapshot is not imported by the terminal. `verify_strategy.py` checks the presence and Python syntax of its 19 source files. Full native signal replay belongs to the Freqtrade research environment and its 5-minute data; terminal reproduction starts from the packaged ledger.
