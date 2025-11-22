"""
Price accessor for retrieving token prices by type (ASK, BID, MID, LIVE, ACTUAL).
"""

from typing import Optional, Dict
from datetime import datetime, timedelta
from decimal import Decimal

from polyarb.data.models import PriceType, OrderBookSnapshot, Trade
from polyarb.data.clob_client import CLOBClient
from sqlalchemy.orm import Session


class PriceAccessor:
    """
    Unified interface for accessing prices by type.
    """
    
    def __init__(
        self,
        clob_client: CLOBClient,
        db_session: Optional[Session] = None,
        live_price_ttl: int = 60
    ):
        """
        Initialize price accessor.
        
        Args:
            clob_client: CLOB client for fetching live prices
            db_session: Database session for historical prices
            live_price_ttl: TTL for LIVE price cache in seconds
        """
        self.clob_client = clob_client
        self.db_session = db_session
        self.live_price_ttl = timedelta(seconds=live_price_ttl)
        
        # In-memory cache for recent prices
        self._price_cache: Dict[tuple, tuple] = {}
    
    async def get_price(
        self,
        token_id: str,
        price_type: PriceType,
        side: str = "buy",  # 'buy' or 'sell'
        user_id: Optional[str] = None
    ) -> Optional[float]:
        """
        Get price for a token by type.
        
        Args:
            token_id: Token ID
            price_type: Type of price to retrieve
            side: 'buy' (use ASK) or 'sell' (use BID) - for directional pricing
            user_id: User ID for ACTUAL price lookups
            
        Returns:
            Price as float, or None if not available
        """
        cache_key = (token_id, price_type, side, user_id)
        
        # Check cache first (except for ACTUAL which should always be fresh)
        if price_type != PriceType.ACTUAL and cache_key in self._price_cache:
            price, timestamp = self._price_cache[cache_key]
            if datetime.utcnow() - timestamp < self.live_price_ttl:
                return price
        
        price = None
        
        if price_type == PriceType.ASK:
            price = await self._get_ask_price(token_id)
        
        elif price_type == PriceType.BID:
            price = await self._get_bid_price(token_id)
        
        elif price_type == PriceType.MID:
            price = await self._get_mid_price(token_id)
        
        elif price_type == PriceType.LIVE:
            price = await self._get_live_price(token_id)
        
        elif price_type == PriceType.ACTUAL:
            price = self._get_actual_price(token_id, user_id)
        
        # Update cache
        if price is not None and price_type != PriceType.ACTUAL:
            self._price_cache[cache_key] = (price, datetime.utcnow())
        
        return price
    
    async def _get_ask_price(self, token_id: str) -> Optional[float]:
        """Get lowest ask (buy) price."""
        orderbook = await self.clob_client.fetch_orderbook(token_id, depth=1)
        
        if not orderbook:
            return None
        
        asks = orderbook.get("asks", [])
        if asks:
            return float(asks[0]["price"])
        
        return None
    
    async def _get_bid_price(self, token_id: str) -> Optional[float]:
        """Get highest bid (sell) price."""
        orderbook = await self.clob_client.fetch_orderbook(token_id, depth=1)
        
        if not orderbook:
            return None
        
        bids = orderbook.get("bids", [])
        if bids:
            return float(bids[0]["price"])
        
        return None
    
    async def _get_mid_price(self, token_id: str) -> Optional[float]:
        """Get mid-market price (bid + ask) / 2."""
        orderbook = await self.clob_client.fetch_orderbook(token_id, depth=1)
        
        if not orderbook:
            return None
        
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        
        if bids and asks:
            bid = float(bids[0]["price"])
            ask = float(asks[0]["price"])
            return (bid + ask) / 2
        
        return None
    
    async def _get_live_price(self, token_id: str) -> Optional[float]:
        """Get last traded price."""
        return await self.clob_client.fetch_last_trade_price(token_id)
    
    def _get_actual_price(
        self, 
        token_id: str, 
        user_id: Optional[str]
    ) -> Optional[float]:
        """
        Get actual execution price from database.
        
        Returns the most recent trade price for this user/token.
        """
        if not self.db_session or not user_id:
            return None
        
        # Query most recent trade for this user and token
        trade = (
            self.db_session.query(Trade)
            .filter(
                Trade.token_id == token_id,
                Trade.user_id == user_id
            )
            .order_by(Trade.execution_timestamp.desc())
            .first()
        )
        
        if trade:
            return float(trade.price)
        
        return None
    
    async def get_prices_batch(
        self,
        token_ids: List[str],
        price_type: PriceType,
        side: str = "buy"
    ) -> Dict[str, Optional[float]]:
        """
        Get prices for multiple tokens.
        
        Args:
            token_ids: List of token IDs
            price_type: Type of price to retrieve
            side: 'buy' or 'sell'
            
        Returns:
            Dictionary mapping token_id to price
        """
        prices = {}
        
        for token_id in token_ids:
            price = await self.get_price(token_id, price_type, side)
            prices[token_id] = price
        
        return prices
    
    def clear_cache(self):
        """Clear the price cache."""
        self._price_cache.clear()
    
    async def get_price_with_fallback(
        self,
        token_id: str,
        preferred_types: list[PriceType],
        side: str = "buy"
    ) -> tuple[Optional[float], Optional[PriceType]]:
        """
        Get price with fallback to alternative price types.
        
        Args:
            token_id: Token ID
            preferred_types: List of price types in order of preference
            side: 'buy' or 'sell'
            
        Returns:
            Tuple of (price, price_type_used) or (None, None)
        """
        for price_type in preferred_types:
            price = await self.get_price(token_id, price_type, side)
            if price is not None:
                return price, price_type
        
        return None, None
