import base64
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from tickcraft.client import KalshiClient
from tickcraft.paper import asks, favorite, fee, Ledger


class Tests(unittest.TestCase):
    def test_fixed_point_depth_and_side(self):
        book = {"orderbook_fp": {"yes_dollars": [[".60", "2"]],
                                "no_dollars": [[".39", "2"]]}}
        quotes = asks(book, 1)
        self.assertEqual(quotes, {"yes": D(".61"), "no": D(".40")})
        self.assertEqual(favorite(quotes, D(".70")), "yes")
        self.assertEqual(asks(book, 3), {})

    def test_legacy_cap_tie_missing(self):
        quotes = asks({"orderbook": {"yes": [[60, 2]], "no": [[39, 2]]}}, 1)
        self.assertIsNone(favorite(quotes, D(".60")))
        self.assertIsNone(favorite({"yes": D(".51"), "no": D(".51")}, D(".70")))
        self.assertEqual(asks({}, 1), {})

    def test_fees(self):
        self.assertEqual(fee(D(".5"), 1, D(".07")), D(".02"))

    def test_restart_dedup_settlement_and_brake(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / "ledger.sqlite")
            ledger = Ledger(path)
            args = ("A", "yes", 1, D(".60"), D(".02"), D(5), D(".50"))
            self.assertTrue(ledger.enter(*args))
            self.assertFalse(ledger.enter(*args))
            ledger.db.close()
            ledger = Ledger(path)
            ledger.settle("A", "")
            self.assertIsNone(ledger.rows()[0]["result"])
            ledger.settle("A", "no")
            ledger.settle("A", "yes")  # cannot silently rewrite a settled result
            self.assertEqual(ledger.totals(), (D(".62"), D("-.62")))
            self.assertFalse(ledger.enter("B", *args[1:]))
            ledger.db.close()

    def test_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            ledger = Ledger(str(Path(temp) / "ledger.sqlite"))
            self.assertFalse(ledger.enter("A", "yes", 1, D(".60"), D(".02"), D(".61"), D(3)))
            ledger.db.close()

    def test_signing(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "key.pem"
            path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                              serialization.PrivateFormat.PKCS8,
                                              serialization.NoEncryption()))
            client = KalshiClient("test-key", str(path))
            headers = client._sign("/trade-api/v2/markets")
            message = (headers["KALSHI-ACCESS-TIMESTAMP"] + "GET/trade-api/v2/markets").encode()
            key.public_key().verify(base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"]),
                                    message, padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                    salt_length=32), hashes.SHA256())
            client.session.close()


if __name__ == "__main__":
    unittest.main()
