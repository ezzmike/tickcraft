import unittest
from unittest.mock import Mock, patch

from tickcraft.client import API, KalshiClient, MAX_MARKET_PAGES


class KalshiClientTests(unittest.TestCase):
    def setUp(self):
        self.client = KalshiClient()
        self.client.session.close()
        self.client.session = Mock()
        self.addCleanup(self.client.close)

    def test_get_returns_json_object_and_uses_get_only(self):
        response = Mock()
        response.json.return_value = {"markets": []}
        self.client.session.get.return_value = response

        self.assertEqual(self.client.get("/markets", limit=100), {"markets": []})

        self.client.session.get.assert_called_once_with(
            f"{API}/markets", params={"limit": 100}, headers={}, timeout=10
        )
        response.raise_for_status.assert_called_once_with()

    def test_get_rejects_invalid_or_non_object_json(self):
        response = Mock()
        response.json.side_effect = ValueError("not json")
        self.client.session.get.return_value = response

        with self.assertRaisesRegex(ValueError, "not valid JSON"):
            self.client.get("/markets")

        response.json.side_effect = None
        response.json.return_value = []
        with self.assertRaisesRegex(ValueError, "JSON object"):
            self.client.get("/markets")

    def test_markets_stops_at_final_page_and_passes_cursor(self):
        self.client.get = Mock(side_effect=[
            {"markets": [{"ticker": "FIRST"}], "cursor": "next-page"},
            {"markets": [{"ticker": "SECOND"}]},
        ])

        self.assertEqual(
            list(self.client.markets("SERIES")),
            [{"ticker": "FIRST"}, {"ticker": "SECOND"}],
        )
        self.assertEqual(
            self.client.get.call_args_list,
            [
                unittest.mock.call(
                    "/markets", series_ticker="SERIES", status="open", limit=100
                ),
                unittest.mock.call(
                    "/markets", series_ticker="SERIES", status="open", limit=100,
                    cursor="next-page"
                ),
            ],
        )

    def test_markets_rejects_bad_pagination_responses(self):
        self.client.get = Mock(side_effect=[
            {"markets": [], "cursor": "again"},
            {"markets": [], "cursor": "again"},
        ])

        with self.assertRaisesRegex(ValueError, "repeated pagination cursor"):
            list(self.client.markets("SERIES"))

        self.client.get = Mock(return_value={"markets": {}})
        with self.assertRaisesRegex(ValueError, "list of markets"):
            list(self.client.markets("SERIES"))

        self.client.get = Mock(return_value={"markets": [], "cursor": 0})
        with self.assertRaisesRegex(ValueError, "cursor must be a string"):
            list(self.client.markets("SERIES"))

    def test_markets_rejects_a_truncated_bounded_crawl(self):
        self.client.get = Mock(side_effect=[
            {"markets": [], "cursor": f"cursor-{page}"}
            for page in range(MAX_MARKET_PAGES)
        ])

        with self.assertRaisesRegex(ValueError, "exceeded"):
            list(self.client.markets("SERIES"))

    def test_market_requires_a_market_object(self):
        self.client.get = Mock(return_value={"market": []})

        with self.assertRaisesRegex(ValueError, "market object"):
            self.client.market("MARKET/ONE")

    def test_context_manager_closes_session(self):
        with patch("tickcraft.client.requests.Session") as session_type:
            with KalshiClient():
                pass

        session_type.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
