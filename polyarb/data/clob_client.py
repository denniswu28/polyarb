"""
CLOB (Central Limit Order Book) API client for orderbook and price data.

CLOB API provides orderbook snapshots, trades, and market prices.
Docs: https://docs.polymarket.com/api-reference/clob-api
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import importlib
import inspect
import httpx
import asyncio

from polyarb.data.models import OrderBookSnapshot, PriceType


class CLOBClient:
    """
    Client for Polymarket CLOB API.
    """
    
    BASE_URL = "https://clob.polymarket.com"
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 10,
        max_retries: int = 3,
        use_py_clob_client: bool = True,
        py_clob_client_kwargs: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize CLOB API client.
        
        Args:
            base_url: Base URL for CLOB API (defaults to production)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=timeout)

        # Optional official client for REST endpoints
        self._py_clob_client = None
        if use_py_clob_client:
            self._py_clob_client = self._init_py_clob_client(
                py_clob_client_kwargs or {}
            )
        
        # Cache for last trade prices with TTL
        self._live_price_cache: Dict[str, Tuple[float, datetime]] = {}
        self._cache_ttl = timedelta(seconds=60)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def fetch_orderbook(
        self,
        token_id: str,
        side: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch orderbook for a token.
        
        Args:
            token_id: Token ID (condition token address)
            side: Optional side filter ("BUY" or "SELL")
            
        Returns:
            Orderbook data or None if not available
        """
        # Prefer py-clob-client if available
        py_kwargs = {"side": side} if side else {}
        orderbook = await self._call_py_clob("get_book", token_id, **py_kwargs)
        normalized = self._normalize_orderbook(orderbook)
        if normalized is not None:
            return normalized

        url = f"{self.base_url}/book"
        params = {"token_id": token_id}
        if side:
            params["side"] = side

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return self._normalize_orderbook(response.json())
        except httpx.HTTPError:
            return None
    
    async def fetch_last_trade_price(self, token_id: str) -> Optional[float]:
        """
        Fetch last traded price for a token.
        
        Args:
            token_id: Token ID
            
        Returns:
            Last trade price or None if not available
        """
        # Check cache first
        if token_id in self._live_price_cache:
            price, timestamp = self._live_price_cache[token_id]
            if datetime.utcnow() - timestamp < self._cache_ttl:
                return price

        trades = await self._call_py_clob("get_trades", market=token_id, limit=1)
        price = self._extract_trade_price(trades)
        if price is None:
            url = f"{self.base_url}/trades"
            params = {
                "market": token_id,
                "limit": 1
            }

            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                trades = response.json()
                price = self._extract_trade_price(trades)
            except httpx.HTTPError:
                pass

        if price is not None:
            self._live_price_cache[token_id] = (price, datetime.utcnow())
            return price

        return None
    
    async def fetch_spread(self, token_id: str) -> Optional[Dict[str, float]]:
        """
        Fetch bid-ask spread for a token.
        
        Args:
            token_id: Token ID
            
        Returns:
            Dictionary with spread metrics or None
        """
        orderbook = await self.fetch_orderbook(token_id)
        
        if not orderbook:
            return None
        
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        
        if not bids or not asks:
            return None
        
        best_bid = float(bids[0]["price"])
        best_ask = float(asks[0]["price"])
        
        if best_bid <= 0 or best_ask <= 0:
            return None
        
        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2
        spread_bps = (spread / mid_price) * 10000 if mid_price > 0 else 0
        
        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "spread_bps": spread_bps,
            "mid_price": mid_price
        }
    
    def parse_orderbook_snapshot(
        self, 
        token_id: str, 
        orderbook_data: Dict[str, Any]
    ) -> OrderBookSnapshot:
        """
        Parse orderbook data into OrderBookSnapshot ORM object.
        
        Args:
            token_id: Token ID
            orderbook_data: Raw orderbook data from API
            
        Returns:
            OrderBookSnapshot instance
        """
        bids = orderbook_data.get("bids", [])
        asks = orderbook_data.get("asks", [])
        
        # Extract best bid/ask
        best_bid = None
        best_bid_size = None
        if bids:
            best_bid = Decimal(str(bids[0]["price"]))
            best_bid_size = Decimal(str(bids[0]["size"]))
        
        best_ask = None
        best_ask_size = None
        if asks:
            best_ask = Decimal(str(asks[0]["price"]))
            best_ask_size = Decimal(str(asks[0]["size"]))
        
        # Calculate mid price and spread
        mid_price = None
        spread_bps = None
        if best_bid and best_ask:
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            if mid_price > 0:
                spread_bps = (spread / mid_price) * Decimal("10000")
        
        return OrderBookSnapshot(
            token_id=token_id,
            timestamp=datetime.utcnow(),
            best_bid=best_bid,
            best_bid_size=best_bid_size,
            best_ask=best_ask,
            best_ask_size=best_ask_size,
            mid_price=mid_price,
            spread_bps=spread_bps,
            bids=[{"price": b["price"], "size": b["size"]} for b in bids[:10]],
            asks=[{"price": a["price"], "size": a["size"]} for a in asks[:10]],
        )
    
    async def fetch_multiple_orderbooks(
        self,
        token_ids: List[str],
        side: Optional[str] = None
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Fetch orderbooks for multiple tokens concurrently.
        
        Args:
            token_ids: List of token IDs
            side: Optional side filter ("BUY" or "SELL")
            
        Returns:
            Dictionary mapping token_id to orderbook data
        """
        tasks = [self.fetch_orderbook(token_id, side) for token_id in token_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        orderbooks = {}
        for token_id, result in zip(token_ids, results):
            if isinstance(result, Exception):
                orderbooks[token_id] = None
            else:
                orderbooks[token_id] = result
        
        return orderbooks
    
    def clear_cache(self):
        """Clear the live price cache."""
        self._live_price_cache.clear()

    @staticmethod
    def _normalize_orderbook(orderbook: Any) -> Optional[Dict[str, Any]]:
        """Ensure orderbook payloads share a consistent shape."""
        if not orderbook:
            return None

        bids = None
        asks = None

        if isinstance(orderbook, dict):
            bids = orderbook.get("bids")
            asks = orderbook.get("asks")
        else:
            bids = getattr(orderbook, "bids", None)
            asks = getattr(orderbook, "asks", None)

        if bids is None and asks is None:
            return None

        def _normalize_levels(levels: Any) -> List[Dict[str, Any]]:
            normalized_levels: List[Dict[str, Any]] = []
            for level in levels or []:
                price = None
                size = None

                if isinstance(level, dict):
                    price = level.get("price") or level.get("p")
                    size = level.get("size") or level.get("s")
                elif isinstance(level, (list, tuple)) and len(level) >= 2:
                    price, size = level[0], level[1]

                if price is None or size is None:
                    continue

                normalized_levels.append({"price": price, "size": size})

            return normalized_levels

        return {
            "bids": _normalize_levels(bids),
            "asks": _normalize_levels(asks)
        }

    def _init_py_clob_client(self, kwargs: Dict[str, Any]):
        """Attempt to initialize py-clob-client if available."""
        candidate_modules = [
            "py_clob_client.client",
            "py_clob_client.async_client",
            "py_clob_client.rest_client",
        ]

        for module_name in candidate_modules:
            try:
                module = importlib.import_module(module_name)
                client_cls = getattr(module, "AsyncRestClient", None)
                if client_cls is None:
                    continue
                return client_cls(base_url=self.base_url, timeout=self.timeout, **kwargs)
            except ImportError:
                continue
            except Exception:
                # If initialization fails, fall back to HTTPX
                continue

        return None

    async def _call_py_clob(self, method_name: str, *args, **kwargs):
        """Call a py-clob-client method if available."""
        if not self._py_clob_client:
            return None

        method = getattr(self._py_clob_client, method_name, None)
        if not method:
            return None

        try:
            result = method(*args, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result
        except Exception:
            return None

    @staticmethod
    def _extract_trade_price(trades: Any) -> Optional[float]:
        """Extract a price float from trades payloads."""
        if not trades:
            return None

        # py-clob-client may return a dict with a "trades" key
        if isinstance(trades, dict) and "trades" in trades:
            trades_list = trades.get("trades") or []
        elif isinstance(trades, dict) and "data" in trades and isinstance(trades["data"], dict):
            trades_list = trades["data"].get("trades") or []
        else:
            trades_list = trades

        if not trades_list:
            return None

        try:
            first_trade = trades_list[0]
            price = float(first_trade.get("price", 0))
            return price
        except Exception:
            return None
