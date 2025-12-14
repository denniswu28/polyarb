"""
Polymarket platform integration.

This module provides integration with the Polymarket prediction market platform.
"""

import logging
import requests
from typing import List, Optional, Dict, Any
from datetime import datetime

from polyarb.platforms.base import PlatformInterface, Market


logger = logging.getLogger(__name__)


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

            payload = response.json()
            if isinstance(payload, dict):
                markets_data = payload.get("markets")
                if markets_data is None:
                    raise ValueError(
                        "Polymarket response missing 'markets' key; "
                        f"available keys: {list(payload.keys())}"
                    )
            elif isinstance(payload, list):
                markets_data = payload
            else:
                raise ValueError(
                    "Unexpected Polymarket response type: "
                    f"{type(payload).__name__}"
                )

            if not markets_data:
                raise ValueError(
                    "Polymarket returned no markets; verify API availability "
                    f"and query params: {params}"
                )

            return [self._parse_market(data) for data in markets_data]

        except requests.RequestException as e:
            raise RuntimeError(
                f"Error fetching markets from Polymarket: {e}"
            ) from e
    
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
            if not isinstance(market_data, dict):
                raise ValueError(
                    "Unexpected Polymarket market payload type: "
                    f"{type(market_data).__name__}"
                )

            return self._parse_market(market_data)

        except requests.RequestException as e:
            raise RuntimeError(
                f"Error fetching market {market_id} from Polymarket: {e}"
            ) from e
    
    def _parse_market(self, data: Dict[str, Any]) -> Market:
        """
        Parse Polymarket API response into Market object.
        
        Args:
            data: Raw market data from API
            
        Returns:
            Market object
        """
        if not isinstance(data, dict):
            raise TypeError(
                "Polymarket market payload must be a dict; "
                f"got {type(data).__name__}"
            )

        market_id = data.get("id") or data.get("condition_id")
        if not market_id:
            raise ValueError("Polymarket market payload missing identifier")

        question = data.get("question")
        if not question:
            raise ValueError(
                f"Market {market_id} missing required question text"
            )

        outcomes: list[str] = []
        prices: Dict[str, float] = {}

        outcome_entries = data.get("outcomes") or data.get("tokens")
        if not outcome_entries:
            raise ValueError(
                f"Market {market_id} missing outcomes; payload keys: {list(data.keys())}"
            )

        outcome_prices = (
            data.get("outcomePrices")
            or data.get("prices")
            or data.get("outcome_prices")
        )

        if tokens and data.get("outcomes") and outcome_prices:
            logger.debug(
                "Market %s provided both tokens and outcome price arrays; "
                "using tokens for outcome pricing.",
                market_id,
            )

        if isinstance(outcome_entries, list) and isinstance(outcome_prices, (list, tuple)):
            if len(outcome_entries) != len(outcome_prices):
                raise ValueError(
                    "Market {mid} outcomes/prices length mismatch "
                    "(outcomes={o_len}, prices={p_len}); payload keys: {keys}".format(
                        mid=market_id,
                        o_len=len(outcome_entries),
                        p_len=len(outcome_prices),
                        keys=list(data.keys()),
                    )
                )

        for idx, entry in enumerate(outcome_entries):
            if isinstance(entry, str):
                outcome_name = entry
                price = None
                if isinstance(outcome_prices, (list, tuple)) and len(outcome_prices) > idx:
                    price = outcome_prices[idx]
            elif isinstance(entry, dict):
                outcome_name = (
                    entry.get("outcome")
                    or entry.get("name")
                    or entry.get("title")
                )
                price = (
                    entry.get("price")
                    or entry.get("last_price")
                    or entry.get("lastPrice")
                )

                if price is None:
                    best_bid = entry.get("best_bid") or entry.get("bestBid")
                    best_ask = entry.get("best_ask") or entry.get("bestAsk")
                    if best_bid is not None and best_ask is not None:
                        price = (float(best_bid) + float(best_ask)) / 2
            else:
                raise TypeError(
                    f"Market {market_id} has unsupported outcome entry type: "
                    f"{type(entry).__name__}"
                )

            if not outcome_name:
                raise ValueError(
                    f"Market {market_id} encountered outcome with no name"
                )

            if price is None:
                raise ValueError(
                    "Market {mid} outcome '{name}' missing price; entry={entry}".format(
                        mid=market_id,
                        name=outcome_name,
                        entry=entry,
                    )
                )

            try:
                prices[outcome_name] = float(price)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Market {market_id} outcome '{outcome_name}' has invalid price: {price}"
                ) from exc

            outcomes.append(outcome_name)

        if len(outcomes) < 2:
            raise ValueError(
                f"Market {market_id} has insufficient outcomes: {outcomes}"
            )

        volume = data.get("volume", data.get("volume_24h"))
        if volume is not None:
            try:
                volume = float(volume)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Market {market_id} has invalid volume value: {volume}"
                ) from exc

        end_date_str = data.get("end_date_iso") or data.get("closed_time")
        end_date = None
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError) as exc:
                raise ValueError(
                    f"Market {market_id} has invalid end date: {end_date_str}"
                ) from exc

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
