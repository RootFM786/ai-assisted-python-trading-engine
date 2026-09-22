# Validation approach

The original development process used deterministic run artefacts and independent post-run checks rather than relying on a single summary result. The public repository retains the mechanics of that approach without publishing private market data or production trade output.

## Public checks

- UTC close-time derivation and candle normalisation.
- Immutable configuration snapshots and deterministic SHA-256 hashes.
- Strict CSV OHLC parsing and chronological ordering.
- State-machine progression with the private decision provider absent.
- Mandatory sink creation and lifecycle handling.
- Independent realised-R and drawdown calculation using synthetic logs.

The public tests validate engineering behaviour, not the performance of a withheld trading strategy.
