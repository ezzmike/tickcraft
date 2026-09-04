import sys
import unittest
from decimal import Decimal
from unittest.mock import Mock, patch

from tickcraft import __main__


class MainTests(unittest.TestCase):
    def test_timestamp_parses_utc_iso8601_time(self):
        self.assertEqual(
            __main__.timestamp("2024-01-01T00:00:00Z"),
            1_704_067_200.0,
        )
        self.assertEqual(
            __main__.timestamp("2024-01-01T01:00:00+01:00"),
            1_704_067_200.0,
        )

    def test_timestamp_rejects_malformed_or_timezone_free_values(self):
        for value in (None, 123, "not-a-time", "2024-01-01T00:00:00"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    __main__.timestamp(value)

    def test_once_uses_no_network_and_closes_public_resources(self):
        client = Mock()
        client.markets.return_value = [
            {"ticker": "BAD-TIME", "open_time": None, "close_time": "not-a-time"},
            None,
        ]
        ledger = Mock()
        ledger.rows.return_value = []
        ledger.totals.return_value = (Decimal("0"), Decimal("0"))

        with patch.object(sys, "argv", ["tickcraft", "--once"]), \
                patch.object(__main__, "KalshiClient", return_value=client), \
                patch.object(__main__, "Ledger", return_value=ledger):
            __main__.main()

        client.markets.assert_called_once_with("KXBTC15M")
        client.market.assert_not_called()
        client.book.assert_not_called()
        ledger.enter.assert_not_called()
        client.close.assert_called_once_with()
        ledger.close.assert_called_once_with()

    def test_closes_client_if_ledger_cannot_open(self):
        client = Mock()

        with patch.object(sys, "argv", ["tickcraft", "--once"]), \
                patch.object(__main__, "KalshiClient", return_value=client), \
                patch.object(__main__, "Ledger", side_effect=OSError("cannot open")):
            with self.assertRaisesRegex(OSError, "cannot open"):
                __main__.main()

        client.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
