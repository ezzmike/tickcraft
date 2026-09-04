"""Small read-only client adapted from the original research API wrapper."""
import base64
import time
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

API = "https://external-api.kalshi.com/trade-api/v2"
MAX_MARKET_PAGES = 10


class KalshiClient:
    """Public data needs no key. Optional RSA signing is retained for future use.

    Deliberately exposes GET only: this MVP cannot submit or cancel live orders.
    """
    def __init__(self, key_id=None, private_key_path=None):
        if bool(key_id) != bool(private_key_path):
            raise ValueError("Supply both key ID and private-key path, or neither")
        self.key_id = key_id
        self.key = None
        if private_key_path:
            with open(private_key_path, "rb") as handle:
                self.key = serialization.load_pem_private_key(handle.read(), password=None)
        self.session = requests.Session()
        retry = Retry(total=2, backoff_factor=1, status_forcelist=[429, 502, 503, 504],
                      allowed_methods=["GET"])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def close(self):
        """Release the underlying HTTP session's pooled connections."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def _sign(self, path):
        timestamp = str(int(time.time() * 1000))
        signature = self.key.sign(
            f"{timestamp}GET{path}".encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=hashes.SHA256().digest_size),
            hashes.SHA256(),
        )
        return {"KALSHI-ACCESS-KEY": self.key_id,
                "KALSHI-ACCESS-TIMESTAMP": timestamp,
                "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode()}

    def get(self, endpoint, **params):
        path = "/trade-api/v2" + endpoint
        response = self.session.get(API + endpoint, params=params,
                                    headers=self._sign(path) if self.key else {},
                                    timeout=10)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as error:
            raise ValueError("Kalshi API response was not valid JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("Kalshi API response must be a JSON object")
        return payload

    def markets(self, series):
        cursor = None
        seen_cursors = set()
        for _ in range(MAX_MARKET_PAGES):  # bounded discovery; no unbounded crawl
            payload = self.get("/markets", series_ticker=series, status="open",
                               limit=100, **({"cursor": cursor} if cursor else {}))
            markets = payload.get("markets")
            if not isinstance(markets, list):
                raise ValueError("Kalshi markets response must contain a list of markets")
            yield from markets
            next_cursor = payload.get("cursor")
            if next_cursor is None or next_cursor == "":
                return
            if not isinstance(next_cursor, str):
                raise ValueError("Kalshi markets response cursor must be a string")
            if next_cursor in seen_cursors:
                raise ValueError("Kalshi API returned a repeated pagination cursor")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        raise ValueError(f"Kalshi markets response exceeded {MAX_MARKET_PAGES} pages")

    def market(self, ticker):
        payload = self.get(f"/markets/{quote(ticker, safe='')}")
        market = payload.get("market")
        if not isinstance(market, dict):
            raise ValueError("Kalshi market response must contain a market object")
        return market

    def book(self, ticker):
        return self.get(f"/markets/{quote(ticker, safe='')}/orderbook", depth=10)
