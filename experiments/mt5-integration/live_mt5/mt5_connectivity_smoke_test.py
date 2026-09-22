"""Read-only MT5 smoke test for an already authenticated local terminal.

No credentials, account identifier, terminal path or order-placement command is
accepted by this public tool.
"""
from __future__ import annotations

import argparse
import sys

from live_mt5 import mt5_broker as broker


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only MT5 connectivity smoke test")
    parser.add_argument("--symbol", required=True, help="Instrument symbol available in the local terminal")
    args = parser.parse_args()
    connected, message = broker.initialize_existing_terminal()
    print(f"[SMOKE] {message}")
    if not connected:
        return 1
    try:
        visible = broker.ensure_symbol_visible(args.symbol)
        print(f"[SMOKE] symbol visible: {visible}")
        print(f"[SMOKE] symbol metadata available: {broker.get_symbol_sizing_info(args.symbol) is not None}")
        print(f"[SMOKE] account snapshot available: {broker.account_snapshot() is not None}")
        return 0 if visible else 1
    finally:
        broker.shutdown()


if __name__ == "__main__":
    sys.exit(main())
