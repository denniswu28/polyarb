"""
Polymarket platform integration.

This module provides integration with the Polymarket prediction market platform.
"""

import requests
from typing import List, Optional, Dict, Any
from datetime import datetime

from polyarb.platforms.base import PlatformInterface, Market


class PolymarketPlatform(PlatformInterface):
    """Integration with Polymarket prediction market platform."""
    
    # Polymarket public API endpoints
    BASE_URL = "https://gamma-api.polymarket.com"
    MARKETS_ENDPOINT = "/markets"
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize Polymarket platform interface.
        
        Args:
            api_key: Optional API key (not required for public endpoints)
            **kwargs: Additional configuration
        """
        super().__init__(api_key, **kwargs)
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})
    
    @property
    def platform_name(self) -> str:
        """Return the platform name."""
        return "Polymarket"
    
    def get_markets(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        active: Optional[bool] = None,
        closed: Optional[bool] = None,
        archived: Optional[bool] = None,
        slug: Optional[str] = None,
        tag_id: Optional[str] = None,
        order: Optional[str] = None,
        ascending: Optional[bool] = None,
    ) -> List[Market]:
        """
        Fetch available markets from Polymarket.

        Args:
            limit: Optional limit on number of markets to fetch
            offset: Pagination offset
            active: Filter by active status
            closed: Filter by closed status
            archived: Filter by archived status
            slug: Filter by slug
            tag_id: Filter by tag ID
            order: Sort field
            ascending: Sort order

        Returns:
            List of Market objects
        """
        try:
            params: Dict[str, Any] = {"offset": offset}

            if limit is not None:
                params["limit"] = limit

            if active is not None:
                params["active"] = "true" if active else "false"

            if closed is not None:
                params["closed"] = "true" if closed else "false"

            if archived is not None:
                params["archived"] = "true" if archived else "false"

            if slug:
                params["slug"] = slug

            if tag_id:
                params["tag_id"] = tag_id

            if order:
                params["order"] = order

            if ascending is not None:
                params["ascending"] = "true" if ascending else "false"
            
            response = self.session.get(
                f"{self.BASE_URL}{self.MARKETS_ENDPOINT}",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            markets_data = response.json()
            return [self._parse_market(data) for data in markets_data]
            
        except requests.RequestException as e:
            print(f"Error fetching markets from Polymarket: {e}")
            return []
    
    def get_market(self, market_id: str) -> Optional[Market]:
        """
        Fetch a specific market by ID from Polymarket.
        
        Args:
            market_id: The unique identifier for the market
            
        Returns:
            Market object if found, None otherwise
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}{self.MARKETS_ENDPOINT}/{market_id}",
                timeout=10
            )
            response.raise_for_status()
            
            market_data = response.json()
            return self._parse_market(market_data)
            
        except requests.RequestException as e:
            print(f"Error fetching market {market_id} from Polymarket: {e}")
            return None
    
    def _parse_market(self, data: Dict[str, Any]) -> Market:
        """
        Parse Polymarket API response into Market object.
        
        Args:
            data: Raw market data from API
            
        Returns:
            Market object
        """
        # Extract market information
        market_id = data.get("id") or data.get("condition_id", "")
        question = data.get("question", "Unknown")
        
        # Parse outcomes and prices
        outcomes = []
        prices = {}
        
        # Polymarket typically has tokens for Yes/No outcomes
        tokens = data.get("tokens", [])
        if tokens:
            for token in tokens:
                outcome = token.get("outcome", "")
                if outcome:
                    outcomes.append(outcome)
                    # Price is typically in the last_trade_price or best_bid/best_ask
                    price = token.get("price", 0.0)
                    prices[outcome] = float(price) if price else 0.0
        else:
            # Fallback for different API response formats
            outcomes = ["Yes", "No"]
            prices = {"Yes": 0.5, "No": 0.5}
        
        # Parse volume and end date
        volume = data.get("volume", data.get("volume_24h"))
        if volume:
            volume = float(volume)
        
        end_date_str = data.get("end_date_iso") or data.get("closed_time")
        end_date = None
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        return Market(
            id=market_id,
            platform=self.platform_name,
            question=question,
            outcomes=outcomes,
            prices=prices,
            volume=volume,
            end_date=end_date,
            metadata=data
        )
