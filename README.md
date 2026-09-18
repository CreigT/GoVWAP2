# GoVWAP2

GoVWAP2 is a deliberately simple, paper-only VWAP trading engine built around one explicit 60-second loop.

## Current loop

For NVDA and QQQ:

1. Load the append-only lot ledger.
2. Get the latest market price and current-session VWAP.
3. Compute today's realized P&L.
4. Evaluate each ticker:
   - Price below VWAP + no open lot + slot available + daily stop not hit -> paper BUY $52.
   - Existing lot + price at or above VWAP + 0.4% -> SELL that exact lot quantity.
   - Otherwise -> HOLD.
5. On a simulated fill, append one event to `lot_ledger.jsonl`.
6. Sleep 60 seconds and repeat.

Run:

```bash
python3 simple_trade.py
```

## Current status

- Repository: GoVWAP2
- Main program: `simple_trade.py`
- Ledger: `lot_ledger.jsonl` (created on first fill)
- Tickers: NVDA, QQQ
- Buy size: $52 notional
- Exit rule: current price >= session VWAP x 1.004
- Poll interval: 60 seconds
- Mode: PAPER ONLY
- Live brokerage execution: intentionally disabled

The program currently stops rather than inventing prices because a real market-data adapter has not yet been connected.

## Next steps

These are the next engineering stages, in order.

### 1. Market-data adapter

Connect a legitimate market-data or broker-paper API for NVDA and QQQ. Retrieve timestamped intraday price/volume bars and reject missing, stale, malformed, or out-of-session data.

### 2. Real session VWAP

Calculate VWAP from actual intraday bars for the current trading session:

`VWAP = sum(price * volume) / sum(volume)`

Define the session boundary and bar interval explicitly. Do not carry yesterday's VWAP into today's decisions.

### 3. Persistent restart-safe state

Make the ledger sufficient to reconstruct every open lot after a process restart. Validate malformed/duplicate events and preserve append-only history.

### 4. Idempotent orders

Create a deterministic `client_order_id` for every intended order so the same signal cannot create duplicate orders after a timeout, crash, or restart.

Expected order identity includes date, ticker, side, signal identity, and the referenced lot for sells.

### 5. Stronger risk controls

Before any order can be admitted, enforce:

- maximum open lots
- maximum daily loss
- maximum daily deployed capital
- one open lot per ticker unless explicitly changed
- stale-data rejection
- market-hours/session checks
- duplicate-order rejection
- emergency kill switch

A failed risk check means no order.

### 6. Paper-broker adapter

Connect the strategy to a broker's sandbox/paper environment. Broker acknowledgements and actual paper fills become authoritative; do not assume an order request equals a fill.

### 7. Reconciliation

At startup and periodically, reconcile the local lot ledger against the paper broker's orders, fills, and positions. Any unexplained mismatch should stop new orders and require review.

### 8. Testing

Test at minimum:

- below-VWAP BUY
- no duplicate BUY while a lot exists
- VWAP +0.4% SELL
- exact-lot quantity on SELL
- daily-stop lockout
- maximum-slot lockout
- restart recovery
- duplicate signal/idempotency
- stale market data
- rejected/cancelled/partial fills
- broker/local-state mismatch
- kill switch

### 9. Paper soak period

Run the complete system in paper mode across multiple market sessions. Record signals, orders, fills, P&L, failures, restarts, and reconciliation results. Strategy profitability must not be assumed from a short test.

### 10. Live-money boundary

Live trading is not part of the current GoVWAP2 build. Changing `DRY_RUN` must never be sufficient to enable real-money execution.

If live trading is considered later, it requires a separately implemented live adapter, explicit credentials/configuration, additional risk limits, reconciliation, monitoring, and an intentional activation step.

## Definition of done for the next milestone

The next milestone is complete when GoVWAP2 can consume real intraday market data, calculate current-session VWAP, generate deterministic decisions, submit them only to a paper broker, survive a restart without duplicate orders, reconstruct its lots, and reconcile its ledger against broker paper fills.

Until then, GoVWAP2 remains a development/paper-trading system.
