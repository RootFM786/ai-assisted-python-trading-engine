# Strategy boundary

The public repository intentionally shows the real engineering system around a confidential decision layer.

## Retained

- Contract/module layout and public integration points.
- Deterministic state ownership, lifecycle handling and guardrails.
- Configuration freezing, hashing, logging, audit artefacts and verification.
- Data adaptation and selected broker connectivity/account-query work.

## Withheld

- Directional-bias, structure, qualification and entry predicates.
- Timing gates, numerical parameters, configuration locks and rule ordering.
- Stop/target selection and production exit-policy details.
- Historical input data, trade records, position-sizing schedule and order sending.

Contracts 8–14 preserve their real roles and call shapes but expose only a `WithheldDecisionProvider`. That makes the boundary reviewable without making the production strategy reproducible.
