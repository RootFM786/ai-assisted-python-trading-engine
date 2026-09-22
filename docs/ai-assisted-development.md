# AI-assisted development workflow

AI was used as an **engineering assistant during development**, not as the runtime trading decision-maker. The core engine is deterministic Python and has no LLM dependency.

## Division of responsibility

| Stage | AI-assisted work | Engineering control |
|---|---|---|
| Requirements | Helped formalise natural-language trading rules into unambiguous statements | Locked source documents remained authoritative; undocumented assumptions were not allowed |
| Architecture | Helped reason about module boundaries, state ownership, determinism and failure cases | Responsibilities and forbidden behaviours were captured in explicit contracts before coding |
| Implementation | Cursor was used for contract-directed code changes | Generated diffs were reviewed against the relevant contract and accepted/rejected rather than treated as authoritative |
| Debugging | AI assisted with tracing mismatches and explaining code paths | Behaviour was checked against logs, fixtures and expected contract semantics |
| Validation | AI helped reason about parity and verification requirements | Deterministic reruns, audit outputs and independent verification scripts were used as the evidence layer |
| Iteration | Helped compare implementations and identify wiring/coverage gaps | Changes were constrained by the frozen V1 scope instead of opportunistically changing the strategy |

## Why this matters

The project was deliberately structured to avoid a weak pattern of “prompt an AI and trust whatever code comes back.” Instead, it used:

**human-defined rules → formal specification → module contracts → AI-assisted implementation → diff/review → deterministic execution → verification**

That separation is visible in the repository itself: the source code can be compared with the original specifications and contract documents, while run outputs contain configuration/audit metadata.

## Runtime boundary

The preserved V1 core executes locally from explicit configuration and normalized market-data inputs. AI is not queried during a backtest and does not make discretionary decisions on individual candles.
