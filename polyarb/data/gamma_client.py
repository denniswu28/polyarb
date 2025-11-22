"""
Gamma API client for fetching Polymarket events and markets.

Gamma API is Polymarket's public API for market data.
Docs: https://docs.polymarket.com/api-reference/gamma-api
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import httpx

from polyarb.data.models import Event, DBMarket, Outcome


class GammaClient:
    """
    Client for Polymarket Gamma API.
    """
    
    BASE_URL = "https://gamma-api.polymarket.com"
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize Gamma API client.
        
        Args:
            base_url: Base URL for Gamma API (defaults to production)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def fetch_events(
        self,
        active: Optional[bool] = True,
        limit: Optional[int] = 100,
        offset: int = 0,
        order_by: str = "volume",
        ascending: bool = False,
        start_date_min: Optional[datetime] = None,
        end_date_min: Optional[datetime] = None,
        end_date_max: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch events from Gamma API.
        
        Args:
            active: Filter by active status
            limit: Maximum number of events to fetch
            offset: Pagination offset
            order_by: Field to order by ('volume', 'end_date', etc.)
            ascending: Sort order
            start_date_min: Minimum start date filter
            end_date_min: Minimum end date filter (e.g., T+7 days)
            end_date_max: Maximum end date filter (e.g., T+49 days)
            
        Returns:
            List of event dictionaries from API
        """
        params = {
            "limit": limit,
            "offset": offset,
            "order": order_by,
            "ascending": "true" if ascending else "false",
        }
        
        if active is not None:
            params["active"] = "true" if active else "false"
        
        if start_date_min:
            params["start_date_min"] = start_date_min.isoformat()
        
        if end_date_min:
            params["end_date_min"] = end_date_min.isoformat()
        
        if end_date_max:
            params["end_date_max"] = end_date_max.isoformat()
        
        url = f"{self.base_url}/events"
        
        for attempt in range(self.max_retries):
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return []
    
    async def fetch_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single event by ID.
        
        Args:
            event_id: Event ID
            
        Returns:
            Event dictionary or None if not found
        """
        url = f"{self.base_url}/events/{event_id}"
        
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None
    
    async def fetch_markets(
        self,
        limit: Optional[int] = 100,
        offset: int = 0,
        active: Optional[bool] = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch markets from Gamma API.
        
        Args:
            limit: Maximum number of markets to fetch
            offset: Pagination offset
            active: Filter by active status
            
        Returns:
            List of market dictionaries from API
        """
        params = {
            "limit": limit,
            "offset": offset,
        }
        
        if active is not None:
            params["active"] = "true" if active else "false"
        
        url = f"{self.base_url}/markets"
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return []
    
    async def fetch_market(self, market_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single market by ID.
        
        Args:
            market_id: Market ID or condition ID
            
        Returns:
            Market dictionary or None if not found
        """
        url = f"{self.base_url}/markets/{market_id}"
        
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None
    
    def parse_events_with_markets(
        self, 
        events_data: List[Dict[str, Any]]
    ) -> tuple[List[Event], List[DBMarket], List[Outcome]]:
        """
        Parse API events data into ORM objects.
        
        Args:
            events_data: List of event dictionaries from API
            
        Returns:
            Tuple of (events, markets, outcomes) lists
        """
        events = []
        markets = []
        outcomes = []
        
        for event_data in events_data:
            # Parse event
            event = Event.from_api_data(event_data)
            events.append(event)
            
            # Parse markets within event
            markets_data = event_data.get("markets", [])
            for market_data in markets_data:
                market = DBMarket.from_api_data(event.id, market_data)
                markets.append(market)
                
                # Parse outcomes within market
                outcomes_data = market_data.get("outcomes", [])
                for outcome_data in outcomes_data:
                    outcome = Outcome.from_api_data(market.id, outcome_data)
                    outcomes.append(outcome)
        
        return events, markets, outcomes
    
    @staticmethod
    def get_default_filters() -> Dict[str, Any]:
        """
        Get default filters for fetching liquid, active events.
        
        Returns:
            Dictionary of filter parameters
        """
        now = datetime.utcnow()
        return {
            "active": True,
            "end_date_min": now + timedelta(days=7),  # At least 7 days until resolution
            "end_date_max": now + timedelta(days=49),  # At most 49 days
            "order_by": "volume",
            "ascending": False,  # Highest volume first
        }
