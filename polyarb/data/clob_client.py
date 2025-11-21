"""
CLOB (Central Limit Order Book) API client for orderbook and price data.

CLOB API provides orderbook snapshots, trades, and market prices.
Docs: https://docs.polymarket.com/api-reference/clob-api
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
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
        max_retries: int = 3
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
        
        # Cache for last trade prices with TTL
        self._live_price_cache: Dict[str, Tuple[float, datetime]] = {}
        self._cache_ttl = timedelta(seconds=60)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def fetch_orderbook(
        self, 
        token_id: str,
        depth: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch orderbook for a token.
        
        Args:
            token_id: Token ID (condition token address)
            depth: Number of price levels to fetch
            
        Returns:
            Orderbook data or None if not available
        """
        url = f"{self.base_url}/book"
        params = {
            "token_id": token_id,
            "depth": depth
        }
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
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
        
        url = f"{self.base_url}/trades"
        params = {
            "token_id": token_id,
            "limit": 1
        }
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            trades = response.json()
            
            if trades and len(trades) > 0:
                price = float(trades[0].get("price", 0))
                # Update cache
                self._live_price_cache[token_id] = (price, datetime.utcnow())
                return price
        except httpx.HTTPError:
            pass
        
        return None
    
    async def fetch_spread(self, token_id: str) -> Optional[Dict[str, float]]:
        """
        Fetch bid-ask spread for a token.
        
        Args:
            token_id: Token ID
            
        Returns:
            Dictionary with spread metrics or None
        """
        orderbook = await self.fetch_orderbook(token_id, depth=1)
        
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
        depth: int = 10
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Fetch orderbooks for multiple tokens concurrently.
        
        Args:
            token_ids: List of token IDs
            depth: Number of price levels to fetch
            
        Returns:
            Dictionary mapping token_id to orderbook data
        """
        tasks = [self.fetch_orderbook(token_id, depth) for token_id in token_ids]
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
