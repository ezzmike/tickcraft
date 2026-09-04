"""Conservative snapshot paper execution; NOT a maker queue simulator."""
import sqlite3
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path

D = Decimal


def _decimal(value, name):
    """Return a finite Decimal or raise a consistent input error."""
    try:
        result = D(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {name}") from error
    if not result.is_finite():
        raise ValueError(f"Invalid {name}")
    return result


def _ticker(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def asks(payload, quantity):
    """Kalshi returns bids; each ask is one minus the opposite best bid."""
    if not isinstance(payload, Mapping):
        raise ValueError("Invalid order book")
    quantity = _decimal(quantity, "quantity")
    if quantity <= 0:
        raise ValueError("Invalid quantity")
    book = payload.get("orderbook_fp")
    fixed = book is not None
    book = book if fixed else payload.get("orderbook", {})
    if not isinstance(book, Mapping):
        raise ValueError("Invalid order book")
    result = {}
    for side, opposite in (("yes", "no"), ("no", "yes")):
        levels = book.get(opposite + "_dollars" if fixed else opposite, [])
        if levels is None:
            levels = []
        if isinstance(levels, (str, bytes)) or not isinstance(levels, Sequence):
            raise ValueError("Invalid order book")
        valid = []
        for level in levels:
            if (isinstance(level, (str, bytes)) or not isinstance(level, Sequence)
                    or len(level) != 2):
                raise ValueError("Invalid order book")
            price, count = level
            price = _decimal(price, "order book") / (1 if fixed else 100)
            count = _decimal(count, "order book")
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
    if not isinstance(quotes, Mapping) or set(quotes) != {"yes", "no"}:
        return None
    cap = _decimal(cap, "cap")
    yes, no = _decimal(quotes["yes"], "quote"), _decimal(quotes["no"], "quote")
    if not 0 < yes < 1 or not 0 < no < 1:
        raise ValueError("Invalid quote")
    if yes == no:
        return None
    side = "yes" if yes > no else "no"
    return side if (yes if side == "yes" else no) <= cap else None


def fee(price, quantity, rate):
    price = _decimal(price, "price")
    quantity = _decimal(quantity, "quantity")
    rate = _decimal(rate, "fee rate")
    if quantity <= 0:
        raise ValueError("Invalid quantity")
    if not 0 <= price <= 1 or rate < 0:
        raise ValueError("Invalid fee inputs")
    return (rate * quantity * price * (1 - price)).quantize(D(".01"), rounding=ROUND_CEILING)


class Ledger:
    def __init__(self, path):
        self.db = None
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path)
            self.db.row_factory = sqlite3.Row
            self.db.execute("""CREATE TABLE IF NOT EXISTS trades (
                ticker TEXT PRIMARY KEY, side TEXT NOT NULL, quantity INTEGER NOT NULL,
                price TEXT NOT NULL, fee TEXT NOT NULL, result TEXT, pnl TEXT,
                entered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            self.db.commit()
        except Exception:
            if self.db is not None:
                self.db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        """Release the SQLite connection. Safe to call more than once."""
        self.db.close()

    def rows(self):
        return list(self.db.execute("SELECT * FROM trades ORDER BY entered_at, ticker"))

    def totals(self):
        rows = self.rows()
        cost = sum((D(r["price"]) * r["quantity"] + D(r["fee"]) for r in rows), D(0))
        pnl = sum((D(r["pnl"]) for r in rows if r["pnl"] is not None), D(0))
        return cost, pnl

    def enter(self, ticker, side, quantity, price, fees, budget, loss_limit):
        if (not _ticker(ticker) or side not in ("yes", "no")
                or isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0):
            return False
        try:
            price = _decimal(price, "price")
            fees = _decimal(fees, "fees")
            budget = _decimal(budget, "budget")
            loss_limit = _decimal(loss_limit, "loss limit")
        except ValueError:
            return False
        if not 0 < price < 1 or fees < 0 or budget <= 0 or loss_limit <= 0:
            return False
        with self.db:
            # Lock before reading totals so concurrent writers cannot both pass a limit.
            self.db.execute("BEGIN IMMEDIATE")
            cost, pnl = self.totals()
            if cost + price * quantity + fees > budget or pnl <= -loss_limit:
                return False
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO trades(ticker,side,quantity,price,fee) VALUES(?,?,?,?,?)",
                (ticker, side, quantity, str(price), str(fees)))
        return cursor.rowcount == 1

    def settle(self, ticker, result):
        if not _ticker(ticker) or result not in ("yes", "no"):
            return  # unresolved/void/nonbinary outcomes require manual review
        with self.db:
            # A single writer sees and settles each open paper trade exactly once.
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT * FROM trades WHERE ticker=?", (ticker,)).fetchone()
            if not row or row["result"] is not None:
                return
            payout = D(row["quantity"]) if row["side"] == result else D(0)
            pnl = payout - D(row["price"]) * row["quantity"] - D(row["fee"])
            self.db.execute("UPDATE trades SET result=?,pnl=? WHERE ticker=?",
                            (result, str(pnl), ticker))
