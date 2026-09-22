# Design-process artefacts

The private development archive contains detailed behaviour extraction, responsibility mapping, wiring-gap analysis and contract-coverage work. This public repository preserves the engineering conclusions without reproducing confidential rules.

## Public evidence retained

- A numbered contract architecture rather than a monolithic script.
- Explicit input/output and state-ownership boundaries.
- A deterministic run harness that does not mutate execution state directly.
- Validation and audit tooling outside the core decision layer.
- An explicit strategy boundary where production predicates are withheld.

The important public lesson is the process: ambiguous manual workflow was converted into testable contracts, then checked against deterministic run artefacts. The exact decision rules remain private.
