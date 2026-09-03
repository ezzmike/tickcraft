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
        return response.json()

    def markets(self, series):
        cursor = None
        for _ in range(10):  # bounded discovery; no unbounded crawl
            payload = self.get("/markets", series_ticker=series, status="open",
                               limit=100, **({"cursor": cursor} if cursor else {}))
            yield from payload.get("markets", [])
            cursor = payload.get("cursor")
            if not cursor:
                return

    def market(self, ticker):
        return self.get(f"/markets/{quote(ticker, safe='')}")["market"]

    def book(self, ticker):
        return self.get(f"/markets/{quote(ticker, safe='')}/orderbook", depth=10)
