"""Run a read-only observer or a bounded-budget forward paper baseline."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import logging
import math
import time

from .client import KalshiClient
from .paper import Ledger, asks, favorite, fee

log = logging.getLogger("tickcraft")


def timestamp(value):
    """Return a finite UTC timestamp from an API ISO-8601 time string."""
    if not isinstance(value, str):
        raise ValueError("Market timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
    except ValueError as error:
        raise ValueError("Market timestamp is not ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Market timestamp must include a timezone")
    result = parsed.timestamp()
    if not math.isfinite(result):
        raise ValueError("Market timestamp must be finite")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", default="KXBTC15M")
    parser.add_argument("--strategy", choices=["observe", "favorite"], default="observe")
    parser.add_argument("--shares", type=int, default=1)
    parser.add_argument("--budget", type=Decimal, default=Decimal("5"))
    parser.add_argument("--loss-limit", type=Decimal, default=Decimal("3"))
    parser.add_argument("--max-price", type=Decimal, default=Decimal(".70"))
    parser.add_argument("--fee-rate", type=Decimal, default=Decimal(".07"))
    parser.add_argument("--slippage", type=Decimal, default=Decimal(".01"))
    parser.add_argument("--interval", type=float, default=10)
    parser.add_argument("--ledger", default="data/paper.sqlite")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    decimals = [args.budget, args.loss_limit, args.max_price, args.fee_rate, args.slippage]
    if (any(not x.is_finite() for x in decimals) or args.shares < 1
            or args.budget <= 0 or args.loss_limit <= 0
            or not 0 < args.max_price < 1 or not 0 <= args.fee_rate <= 1
            or not 0 <= args.slippage < 1 or not 5 <= args.interval <= 3600):
        parser.error("Invalid numeric parameter; interval must be 5..3600 seconds")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    client = ledger = None
    try:
        client = KalshiClient()
        ledger = Ledger(args.ledger)
        log.info("PAPER/READ-ONLY ONLY; no live-order implementation")
        while True:
            try:
                # Resolve old positions before evaluating any new entry.
                for row in ledger.rows():
                    if row["result"] is None:
                        market = client.market(row["ticker"])
                        if market.get("status") == "settled":
                            ledger.settle(row["ticker"], market.get("result"))
                seen = {r["ticker"] for r in ledger.rows()}
                for market in client.markets(args.series):
                    if not isinstance(market, dict):
                        log.warning("Ignoring malformed market record")
                        continue
                    ticker = market.get("ticker")
                    if not isinstance(ticker, str) or not ticker:
                        log.warning("Ignoring market without a ticker")
                        continue
                    try:
                        opened = timestamp(market.get("open_time"))
                        closes = timestamp(market.get("close_time"))
                    except ValueError:
                        log.warning("Ignoring market with invalid timestamps: %s", ticker)
                        continue
                    now = time.time()
                    age = now - opened
                    remaining = closes - now
                    # Example timing only: avoid unopened/closing markets.
                    if age < 30 or remaining < 60 or ticker in seen:
                        continue
                    started = time.monotonic()
                    book = client.book(ticker)
                    if time.monotonic() - started > 2:
                        continue  # fail closed after slow/retried requests
                    if closes - time.time() < 60:
                        continue
                    quotes = asks(book, args.shares)
                    log.info("%s asks=%s", ticker, quotes)
                    if args.strategy == "observe":
                        continue
                    side = favorite(quotes, args.max_price)
                    if not side:
                        continue
                    price = quotes[side] + args.slippage
                    if price > args.max_price or price >= 1:
                        continue
                    fees = fee(price, args.shares, args.fee_rate)
                    if ledger.enter(ticker, side, args.shares, price, fees,
                                    args.budget, args.loss_limit):
                        log.info("PAPER BUY %s %s x%s @ %s fee=%s",
                                 ticker, side, args.shares, price, fees)
                cost, pnl = ledger.totals()
                log.info("cumulative_cost=%s settled_pnl=%s", cost, pnl)
            except (OSError, ValueError, KeyError, TypeError) as error:
                # No synthetic fills or guessed settlements on failed data.
                log.warning("Data unavailable; abstaining: %s", type(error).__name__)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log.info("Stopped. Ledger retained; restart to reconcile open paper positions.")
    finally:
        try:
            if client is not None:
                client.close()
        finally:
            if ledger is not None:
                ledger.close()


if __name__ == "__main__":
    main()
