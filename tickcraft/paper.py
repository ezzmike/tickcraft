"""Conservative snapshot paper execution; NOT a maker queue simulator."""
import sqlite3
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

D = Decimal


def asks(payload, quantity):
    """Kalshi returns bids; each ask is one minus the opposite best bid."""
    book = payload.get("orderbook_fp")
    fixed = book is not None
    book = book if fixed else payload.get("orderbook", {})
    result = {}
    for side, opposite in (("yes", "no"), ("no", "yes")):
        levels = book.get(opposite + "_dollars" if fixed else opposite, [])
        valid = []
        for price, count in levels or []:
            price = D(str(price)) / (1 if fixed else 100)
            count = D(str(count))
            if not price.is_finite() or not count.is_finite():
                raise ValueError("Non-finite order book")
            if not 0 < price < 1 or count < 0:
                raise ValueError("Invalid order book")
            if count > 0:
                valid.append((price, count))
        if valid:
            price, count = max(valid)
            if count >= quantity:  # no imaginary depth or partial fills
                result[side] = 1 - price
    return result


def favorite(quotes, cap):
    """Example baseline, not a validated edge. Equal quotes abstain."""
    if len(quotes) != 2 or quotes["yes"] == quotes["no"]:
        return None
    side = max(quotes, key=quotes.get)
    return side if quotes[side] <= cap else None


def fee(price, quantity, rate):
    return (rate * quantity * price * (1 - price)).quantize(D(".01"), rounding=ROUND_CEILING)


class Ledger:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS trades (
            ticker TEXT PRIMARY KEY, side TEXT NOT NULL, quantity INTEGER NOT NULL,
            price TEXT NOT NULL, fee TEXT NOT NULL, result TEXT, pnl TEXT,
            entered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        self.db.commit()

    def rows(self):
        return list(self.db.execute("SELECT * FROM trades ORDER BY entered_at, ticker"))

    def totals(self):
        rows = self.rows()
        cost = sum((D(r["price"]) * r["quantity"] + D(r["fee"]) for r in rows), D(0))
        pnl = sum((D(r["pnl"]) for r in rows if r["pnl"] is not None), D(0))
        return cost, pnl

    def enter(self, ticker, side, quantity, price, fees, budget, loss_limit):
        cost, pnl = self.totals()
        if cost + price * quantity + fees > budget or pnl <= -loss_limit:
            return False
        with self.db:
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO trades(ticker,side,quantity,price,fee) VALUES(?,?,?,?,?)",
                (ticker, side, quantity, str(price), str(fees)))
        return cursor.rowcount == 1

    def settle(self, ticker, result):
        if result not in ("yes", "no"):
            return  # unresolved/void/nonbinary outcomes require manual review
        row = self.db.execute("SELECT * FROM trades WHERE ticker=?", (ticker,)).fetchone()
        if not row or row["result"] is not None:
            return
        payout = D(row["quantity"]) if row["side"] == result else D(0)
        pnl = payout - D(row["price"]) * row["quantity"] - D(row["fee"])
        with self.db:
            self.db.execute("UPDATE trades SET result=?,pnl=? WHERE ticker=?",
                            (result, str(pnl), ticker))
