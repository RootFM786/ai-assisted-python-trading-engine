# Public contract index

The repository retains the original numbered-contract layout to make the engineering traceable. Contracts 0–7 and 15–16 describe orchestration, identity, clock semantics, configuration, execution mode, adapters, state and sinks. Contracts 8–14 are public-safe integration boundaries whose production decision criteria are withheld.

| Contract | Public evidence |
|---|---|
| 0 | Run lifecycle, audit creation and adapter orchestration remain visible. |
| 1–5 | Identity, time semantics, config mechanics, execution mode and CSV adaptation remain visible. |
| 6–7 | Deterministic state advancement and capacity-policy mechanism remain visible. |
| 8–13 | Real module names, construction, typed boundaries and lifecycle remain; decision predicates and parameters are withheld. |
| 14 | No-mutation outcome-update contract remains; production exit policy is withheld. |
| 15–16 | Sink lifecycle and audit/diagnostic infrastructure remain; strategy-specific provenance and formulas are removed. |
