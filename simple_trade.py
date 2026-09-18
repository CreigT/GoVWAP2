#!/usr/bin/env python3
"""GoVWAP2 singular paper-trading loop.

This build intentionally does NOT contain live-money execution.
Market data and paper fills are adapter functions so the loop can be tested
without accidentally granting brokerage authority.
"""

import json
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

TICKERS = ("NVDA", "QQQ")
BUY_NOTIONAL_USD = 52.0
EXIT_ABOVE_VWAP = 0.004
POLL_SECONDS = 60
MAX_OPEN_LOTS = 2
DAILY_STOP_USD = -20.0
LEDGER = Path("lot_ledger.jsonl")
DRY_RUN = True  # Guardrail: this implementation supports paper fills only.


@dataclass
class Lot:
    lot_id: str
    ticker: str
    qty: float
    entry_price: float
    opened_at: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_events() -> list[dict]:
    if not LEDGER.exists():
        return []
    events = []
    with LEDGER.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def append_event(event: dict) -> None:
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, separators=(",", ":")) + "\n")
        fh.flush()


def load_open_lots(events: list[dict]) -> dict[str, Lot]:
    lots: dict[str, Lot] = {}
    for event in events:
        if event["event"] == "BUY_FILL":
            lot = Lot(
                lot_id=event["lot_id"],
                ticker=event["ticker"],
                qty=float(event["qty"]),
                entry_price=float(event["price"]),
                opened_at=event["ts"],
            )
            lots[lot.lot_id] = lot
        elif event["event"] == "SELL_FILL":
            lots.pop(event["lot_id"], None)
    return lots


def realized_pnl_today(events: list[dict]) -> float:
    today = datetime.now(timezone.utc).date()
    buys = {e["lot_id"]: e for e in events if e["event"] == "BUY_FILL"}
    pnl = 0.0
    for event in events:
        if event["event"] != "SELL_FILL":
            continue
        if datetime.fromisoformat(event["ts"]).date() != today:
            continue
        buy = buys.get(event["lot_id"])
        if buy:
            pnl += (float(event["price"]) - float(buy["price"])) * float(event["qty"])
    return pnl


def get_last_and_vwap(ticker: str) -> tuple[float, float]:
    """Replace with a market-data adapter. Never fabricate prices."""
    raise NotImplementedError(
        f"No market-data adapter configured for {ticker}. "
        "Connect a paper/sandbox data source before running the loop."
    )


def paper_buy(ticker: str, price: float) -> dict:
    qty = BUY_NOTIONAL_USD / price
    return {
        "event": "BUY_FILL",
        "ts": utc_now(),
        "lot_id": str(uuid.uuid4()),
        "ticker": ticker,
        "side": "BUY",
        "notional_usd": BUY_NOTIONAL_USD,
        "qty": qty,
        "price": price,
        "mode": "PAPER",
    }


def paper_sell(lot: Lot, price: float) -> dict:
    return {
        "event": "SELL_FILL",
        "ts": utc_now(),
        "lot_id": lot.lot_id,
        "ticker": lot.ticker,
        "side": "SELL",
        "qty": lot.qty,
        "price": price,
        "mode": "PAPER",
    }


def run() -> None:
    if not DRY_RUN:
        raise RuntimeError(
            "Live trading is intentionally disabled in GoVWAP2. "
            "DRY_RUN=False does not unlock brokerage execution."
        )

    while True:
        events = read_events()
        open_lots = load_open_lots(events)
        pnl = realized_pnl_today(events)
        stop_hit = pnl <= DAILY_STOP_USD

        for ticker in TICKERS:
            try:
                last, vwap = get_last_and_vwap(ticker)
            except NotImplementedError as exc:
                print(exc)
                return

            ticker_lots = [lot for lot in open_lots.values() if lot.ticker == ticker]

            if (
                last < vwap
                and not ticker_lots
                and len(open_lots) < MAX_OPEN_LOTS
                and not stop_hit
            ):
                fill = paper_buy(ticker, last)
                append_event(fill)
                open_lots[fill["lot_id"]] = Lot(
                    lot_id=fill["lot_id"],
                    ticker=ticker,
                    qty=fill["qty"],
                    entry_price=fill["price"],
                    opened_at=fill["ts"],
                )
                print("BUY", ticker, fill["lot_id"])
                continue

            for lot in ticker_lots:
                if last >= vwap * (1.0 + EXIT_ABOVE_VWAP):
                    append_event(paper_sell(lot, last))
                    open_lots.pop(lot.lot_id, None)
                    print("SELL", ticker, lot.lot_id)

            print("HOLD", ticker, "last=", last, "vwap=", vwap, "pnl=", pnl)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()
