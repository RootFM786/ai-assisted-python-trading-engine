# Market data

Historical market datasets are intentionally **not committed** to this portfolio repository.

The core CSV adapter expects normalized candle data with at least:

```text
time,open,high,low,close
```

Timestamps must be timezone-aware UTC values. The engine derives candle-close timing from the adapter data and rejects incompatible timing/format assumptions rather than silently guessing.

Place compatible files outside version control and reference them from a local copied configuration. The repository contains no market data.
