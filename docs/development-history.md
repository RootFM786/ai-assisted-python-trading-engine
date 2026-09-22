# Development history

This repository is a curated reconstruction from the preserved development archive. It deliberately separates the mature V1 engine from older prototypes and later strategy experiments.

## 1. Pearls Planner → mechanical strategy definition

The project began as a rule-based, multi-timeframe workflow with staged qualification, deterministic outcome handling and explicit time semantics. The aim was to eliminate discretionary interpretation so the same inputs would lead to the same decisions. The production qualification criteria and rule combination remain private.

## 2. January 2026 — pre-code specification and contract design

Before implementation, V1 scope was frozen. Three documents became authoritative:

1. **Workflow** — trade eligibility / WHAT.
2. **Mechanical Appendix** — calculations and measurement / HOW.
3. **Canonical Execution Engine** — evaluation order, state and logging / WHEN.

The project then extracted module responsibilities, input/output/state ownership and forbidden behaviours into explicit contracts. A prior monolithic script was analysed for behaviour, wiring gaps and coverage before the modular implementation was allowed to become the source of truth. Evidence of that process is retained in [`docs/design-process/`](design-process/).

## 3. February 2026 — contract-led Python implementation

The V1 spine was implemented as separate Python modules for orchestration, data, state, strategy stages, outcome handling and audit/diagnostic sinks.

## 4. Late February / March 2026 — iteration and verification

The preserved mature XAUUSD branch contains later revisions to multiple core modules plus tooling for:

- outcome checks against M5 candles;
- realised-R recomputation;
- configuration verification;
- timezone/data checks;
- backtest breakdowns;
- parity comparison and archived run outputs.

The public `src/` package is taken from this more mature branch rather than the earlier Phase-0 copy.

## 5. April 2026 — later research branches

The archive later branches into additional NAS100/XAUUSD experiments and a MetaTrader 5 connectivity/execution layer. A small credential-free subset is retained under [`experiments/mt5-integration/`](../experiments/mt5-integration/) to show the integration work without presenting it as part of the locked V1 architecture.

## Selected historical evidence

The following redacted captures provide contemporaneous evidence of the research and integration work. They are historical development artefacts, not live recommendations or performance forecasts.

![Historical research report](../evidence/historical-research-report.jpg)

*Historical research report summarising trade count, aggregate R, expectancy and drawdown. Strategy-specific report naming and exit details were excluded.*

![Multi-instrument organisation](../evidence/historical-multi-instrument-organisation.jpg)

*Instrument-scoped code, data and configuration organisation during development. Parameter-bearing filenames and run outputs are excluded from the public reconstruction.*

![MT5 automated-run evidence](../evidence/historical-mt5-automated-run.jpg)

*MT5-connected automated-run harness during development testing. Paths, symbol, trade criteria, prices, sizing and account data are redacted.*

## What is intentionally excluded

The original archive contains virtual environments, duplicate versions, large historical datasets, hundreds of run folders and strategy experiments. They are useful development evidence but poor public-repository material, so they are not copied here.
