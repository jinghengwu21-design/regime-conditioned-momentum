# Architecture decisions

## ADR 001 — Keep execution and research separate

Freqtrade remains the source of frozen strategy execution. The research terminal reads a portable ledger and market attachment. This preserves the original fills while allowing the UI, diagnostics and Agent runtime to evolve independently. Reproduction of terminal results needs only the bundled files.

## ADR 002 — React terminal, Python research service

The terminal uses React, TypeScript and ECharts. Python owns the analysis dataset and Agent execution. A small loopback HTTP adapter serves the built client and two typed endpoints. The same frontend can be deployed to static hosting with archived research runs.

Static hosting was chosen for the public research snapshot because it is fast to open, has no credential setup and does not expose a model endpoint. Local execution uses the same browser interface with additional run controls.

## ADR 003 — Independent numeric review

The calculation engine uses pandas; the reviewer uses the Python standard library and raw CSV records. Costs are independently reconstructed from fill amount × price. An engine mismatch stops export. A narrative mismatch retains the rejected draft, replaces it with evidence-bound claims and requires another review.

This is deliberately narrower than general fact verification. It checks defined financial metrics, units, citations and configured external-text cases; qualitative interpretation is not a theorem-proving task.

## ADR 004 — No fabricated benchmark observations

The account ledger extends beyond the last complete packaged market day. The benchmark chart therefore compares only the intersecting complete-day window. It uses a synthetic unlevered BTC holding with entry and liquidation fees, while the headline account metrics retain the full native ledger boundary.

## ADR 005 — Preserve strategy identity

The 19-file strategy snapshot retains the historical inheritance chain and class names. The source manifest lists files and the archived strategy class; verification checks Python syntax. Current documentation explains the active rule path and maps it to the RCM-3F research name.

## ADR 006 — Evaluation at three interfaces

Python tests cover metric definitions, the model SDK contract and a real loopback HTTP server. Node tests compare the interactive cost model against Python for every packaged period and scenario. Browser checks exercise period selection, monthly drilldown, trade details, downloads, numeric correction and responsive layout.

Model API contract tests use simulated HTTP responses. Live-provider behaviour requires configured server credentials and is recorded separately from these deterministic tests.
