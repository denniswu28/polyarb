"""
Base platform interface for prediction market platforms.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Market:
    """Represents a market on a platform."""
    
    id: str
    platform: str
    question: str
    outcomes: List[str]
    prices: Dict[str, float]  # outcome -> price
    volume: Optional[float] = None
    end_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def get_price(self, outcome: str) -> Optional[float]:
        """Get the platform's reference/display price for an outcome."""
        return self.prices.get(outcome)

    def get_executable_price(self, outcome: str, side: str) -> Optional[float]:
        """Return an explicitly supplied executable ask or bid.

        ``prices`` remains the backward-compatible reference/display mapping. The
        research engine only treats quotes in ``metadata['asks']`` and
        ``metadata['bids']`` as executable when ``price_semantics`` is explicitly
        ``'executable'``. This prevents midpoint and last-trade values from being
        silently treated as order-book prices.
        """
        metadata = self.metadata or {}
        if metadata.get("price_semantics") != "executable":
            return None

        side_key = {"buy": "asks", "sell": "bids"}.get(side.lower())
        if side_key is None:
            raise ValueError("side must be 'buy' or 'sell'")

        quotes = metadata.get(side_key)
        if not isinstance(quotes, dict):
            return None

        value = quotes.get(outcome)
        if value is None:
            return None
        try:
            price = float(value)
        except (TypeError, ValueError):
            return None
        return price if 0 < price <= 1 else None


class PlatformInterface(ABC):
    """Abstract base class for prediction market platform integrations."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize the platform interface.
        
        Args:
            api_key: Optional API key for the platform
            **kwargs: Additional platform-specific configuration
        """
        self.api_key = api_key
        self.config = kwargs
        self._initialized = False
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the name of the platform."""
        pass
    
    @abstractmethod
    def get_markets(self, limit: Optional[int] = None) -> List[Market]:
        """
        Fetch available markets from the platform.
        
        Args:
            limit: Optional limit on number of markets to fetch
            
        Returns:
            List of Market objects
        """
        pass
    
    @abstractmethod
    def get_market(self, market_id: str) -> Optional[Market]:
        """
        Fetch a specific market by ID.
        
        Args:
            market_id: The unique identifier for the market
            
        Returns:
            Market object if found, None otherwise
        """
        pass
    
    def search_markets(self, query: str) -> List[Market]:
        """
        Search for markets matching a query.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching Market objects
        """
        # Default implementation - can be overridden by platforms with search APIs
        all_markets = self.get_markets()
        query_lower = query.lower()
        return [
            market for market in all_markets 
            if query_lower in market.question.lower()
        ]
    
    def initialize(self) -> bool:
        """
        Mark the local interface initialized without validating a connection.

        Concrete adapters that require validation must override this method.
        
        Returns:
            True when the local state transition succeeds
        """
        try:
            self._initialized = True
            return True
        except Exception:
            self._initialized = False
            return False
    
    @property
    def is_initialized(self) -> bool:
        """Check if the platform is initialized."""
        return self._initialized
