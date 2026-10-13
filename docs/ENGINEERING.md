# Engineering case study

## Turning a strategy archive into an inspectable research system

The original research environment already owned the signal logic, Freqtrade backtest and execution ledger. RCM builds a research application around the archived strategy and execution ledger. Reimplementing the trading engine would create a second source of truth without improving the research interface.

The data adapter exports a narrow, portable ledger. `manifest.json` identifies the source snapshot, market window and transformed CSV files. Source paths, time boundaries and file inventory remain directly readable. The original strategy files are separately preserved in `strategy/frozen/` and are not imported by the web service.

## Strategy research engineering

The historical workflow separated event diagnostics from native account replay. Candidate pools, overlapping signals, single-position blocking, capital reservation and actual fills were reconciled explicitly. Research branches included rule-teacher XGBoost, rolling GMM/XGBoost state inference, factor substitutions and execution-lifecycle analysis. The retained system uses rule-based regimes; model infrastructure remains a research result.

The current archive exposes 48 decisions across 12 families. Its content is stored once and built into browser data, CSV, individual notes and a chronological study. Readers can search failure mechanisms, compare research questions and inspect the basis for retaining a rule.

## Calculation and independent review

The primary engine uses pandas for equity, calendar returns, drawdown and cost attribution. The reviewer in `audit.py` reads CSV records using the standard library and recalculates the values independently. Sharing one arithmetic function between the engine and reviewer would allow the same bug to pass both sides.

A report claim carries a metric, numeric value, unit and evidence ID. Review checks the number and its provenance. The UI formats percentages only after the ratio is calculated; it does not parse prose to recover numbers.

## A recorded correction

The `numeric_mismatch` experiment adds 100 percentage points to the draft's cumulative return. It does not alter the ledger or calculator. The original draft reports 1781.58%; the reviewer computes 1681.58%, records `NUMERIC_MISMATCH`, and rejects the draft. The repair node rebuilds the conclusion from verified evidence and submits it to a second review.

The original draft, both review events and final report remain in the execution record. See `examples/evaluation/EVAL-04/` and the Agent workspace. This is an injected failure with a deterministic correction path, not an estimate of model hallucination frequency.

## Prompt contracts

`prompts/researcher.v1.txt` is the initial prose-oriented contract. Version 2 introduces structured claims, explicit evidence and stricter tool boundaries. `scripts/prompt_contract_replay.py` replays an intentionally incorrect 999-trade claim: free prose has no numeric contract, whereas the structured claim is rejected against the 922-trade ledger. The recorded comparison is a local contract test rather than a live-model A/B experiment.

## Product and engineering iterations

1. Establish the deterministic research loop and provider contract tests around the existing data.
2. Move the presentation into a React terminal with shared scope, trade drilldown, browser cost attribution and separate Agent experiments. Review OpenBB, QuantStats, FinRobot and TradingAgents at the source level; record the adopted decisions in [design references](BENCHMARKS.md).
3. Reconcile browser calculations against Python across four periods and three fees. Split workspace modules, improve font hierarchy, correct subperiod CAGR labels, and fix modal focus so search input survives rerenders.
4. Verify real local HTTP execution, downloadable filtered data, desktop interactions and mobile document widths. Lock dependencies, preserve font licenses and publish build/test workflows with the application.
5. Run the repository on fresh Linux and Windows workers. The Windows worker exposed a legacy-console encoding failure after the behavioral evaluation had completed; make CLI JSON explicitly UTF-8 and reproduce the failure condition in a subprocess regression test.

6. Organize the original strategy history into a research-first site. Add the archive, case comparison, mechanism/evidence reading, version-window comparison and interactive research-loop episodes. Keep source paths and version metadata as the readable provenance model.

The review artifacts and commands are listed in [Verification](VERIFICATION.md). Future changes to the calculation contract should update Python, browser fixtures and the independent review together.
