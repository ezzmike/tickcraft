# Tickcraft

A tiny, paper-first workbench for automated Kalshi strategies.

**MVP, not a proven trading edge. No live order submission is implemented.**
Default mode observes public market data without credentials. No Docker,
dashboard, NAS, model training, or background services are required.

## Quick start

Python 3.11+:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -e .
python -m tickcraft --once
```

Run the illustrative favorite-to-settlement paper baseline:

```sh
python -m tickcraft --strategy favorite --shares 1 --budget 5 --loss-limit 3
```

Stop with Ctrl+C. State lives in ignored `data/paper.sqlite`; restarting with
the same ledger reconciles previously open paper positions and prevents
duplicate entries. Only one process should own a ledger. Keep parameters frozen
per experiment; use `--ledger data/new-experiment.sqlite` for a new cohort.

## What it does

- Reuses the original research project's small API/RSA-PSS signing design.
- Fetches Kalshi public markets and order books with bounded GET retries.
- Correctly converts opposite-side bids into asks, using decimal arithmetic.
- Exposes a small strategy function: `tickcraft.paper.favorite`.
- Records one paper entry per market, fees, official settlement, and net P&L.
- Caps cumulative acquisition spending and halts new entries at a settled-loss
  limit. Settlement reconciliation continues while entries are blocked.

The example buys the side with the higher executable ask, at the first observed
eligible snapshot at least 30 seconds after open and at least 60 seconds before
close. Ties, insufficient displayed best-level depth, and prices over the cap
abstain. This is a plumbing baseline, **not a recommended or optimized strategy**.

## Execution limitations

Paper fills are hypothetical taker fills at the displayed ask plus configurable
slippage (default $0.01/share), requiring full best-level depth. They are not
exchange fills, atomic snapshots, or realistic maker-queue replay. The observed
book may move before an actual order arrives. A response taking over two
seconds is rejected, but HTTP speed does not prove source freshness.

The configurable fee coefficient defaults to 0.07 with per-order cent rounding.
It is an assumption, not automatic series-specific fee discovery. Verify the
current exchange fee schedule before interpreting economics. No taker fallback,
TP, stop-loss liquidation, fractional-size execution, or live routing is shipped.

The loss limit uses settled P&L and is not a guaranteed maximum loss; outstanding
positions can lose more. The cumulative spending budget includes modeled fees.
Unknown/void results remain unresolved for manual review. Polling can miss
opportunities. A stopped process does not reconcile until restarted.

## Lessons retained

1. Market count, not contract count, is the independent sample size.
2. Quotes touching an order are not evidence of maker fills.
3. Fees, spread, depth, delayed data, and partial fills can erase apparent edges.
4. Use chronological holdouts and frozen forward cohorts; do not promote the
   winner of a large threshold search on that same history.
5. A proxy BTC feed is not official settlement data or a guaranteed arbitrage.
6. Profitability, especially across regimes, must be demonstrated rather than
   promised.

No old account data, private credentials, infrastructure addresses, or Git
history was imported. Public API access remains subject to exchange terms and
availability.

## Tests

GitHub Actions runs the offline test suite on pushes and pull requests using
Python 3.12. CI requires no exchange credentials and never starts a trader.

```sh
python -m unittest discover -s tests -v
```

## License and commercial use

[MIT](LICENSE). You may sell software and services built on this code, including
proprietary derivatives, subject to preserving the required notice. Others
receive the same reuse rights; publishing MIT code does not reserve exclusive
commercial rights. Third-party dependencies retain their own licenses. This
repository does not license Kalshi data or grant exchange access.

References: [Kalshi order books](https://docs.kalshi.com/getting_started/orderbook_responses),
[MIT terms](https://opensource.org/license/mit).

Not affiliated with Kalshi. Experimental software, no warranty, no promise of
profit, and no financial advice.
