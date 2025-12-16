"""
Polymarket platform integration.

This module provides integration with the Polymarket prediction market platform.
"""

import ast
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import requests

from polyarb.platforms.base import PlatformInterface, Market


logger = logging.getLogger(__name__)


class PolymarketPlatform(PlatformInterface):
    """Integration with Polymarket prediction market platform."""
    
    # Polymarket public API endpoints
    BASE_URL = "https://gamma-api.polymarket.com"
    EVENTS_ENDPOINT = "/events"
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
        limit: Optional[int] = 100000,
        offset: int = 0,
        active: Optional[bool] = True,
        closed: Optional[bool] = False,
        archived: Optional[bool] = False,
        slug: Optional[str] = None,
        tag_id: Optional[str] = None,
        order: Optional[str] = "liquidity",
        ascending: Optional[bool] = False,
        liquidity_num_min: Optional[float] = None,
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
            liquidity_num_min: Minimum liquidity for markets returned

        Returns:
            List of Market objects
        """
        try:
            params: Dict[str, Any] = {"offset": offset}
            if limit is not None:
                params["limit"] = limit

            if slug:
                params["slug"] = slug
            if tag_id:
                params["tag_id"] = tag_id
            if active is not None:
                params["active"] = "true" if active else "false"
            if closed is not None:
                params["closed"] = "true" if closed else "false"
            if archived is not None:
                params["archived"] = "true" if archived else "false"

            response = self.session.get(
                f"{self.BASE_URL}{self.EVENTS_ENDPOINT}",
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            events_data: List[Dict[str, Any]]

            if isinstance(payload, list):
                events_data = payload
            elif isinstance(payload, dict):
                events_data = (
                    payload.get("events")
                    or payload.get("data")
                    or payload.get("results")
                    or []
                )
                if isinstance(events_data, dict):
                    events_data = [events_data]
            else:
                raise ValueError(
                    "Unexpected Polymarket response type: "
                    f"{type(payload).__name__}"
                )

            if not events_data:
                raise ValueError(
                    "Polymarket returned no events; verify API availability "
                    f"and query params: {params}"
                )

            all_markets: List[Market] = []
            for event_data in events_data:
                markets_data = self._coerce_sequence(
                    event_data.get("markets"),
                    label="markets",
                    market_id=event_data.get("id") or "event",
                )
                for market_data in markets_data:
                    if market_data["active"]:
                        market = self._parse_market(market_data)
                        event_id = event_data.get("id")
                        if event_id:
                            market.metadata = {**(market.metadata or {}), "event_id": event_id}
                        all_markets.append(market)

            if order:
                all_markets.sort(
                    key=lambda m: m.prices.get("Yes", 0)
                    if order == "price"
                    else m.volume or 0,
                    reverse=not ascending,
                )

            if liquidity_num_min is not None:
                all_markets = [
                    m for m in all_markets if (m.volume or 0) >= liquidity_num_min
                ]

            return all_markets

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
        print(question)
        if not question:
            raise ValueError(
                f"Market {market_id} missing required question text"
            )

        outcomes: list[str] = []
        prices: Dict[str, float] = {}

        tokens_data = self._coerce_sequence(
            data.get("tokens"), label="tokens", market_id=market_id
        )

        outcomes_data = self._coerce_sequence(
            data.get("outcomes"), label="outcomes", market_id=market_id
        )

        outcome_entries = tokens_data or outcomes_data
        if not outcome_entries:
            raise ValueError(
                f"Market {market_id} missing outcomes; payload keys: {list(data.keys())}"
            )

        outcome_prices_raw = (
            data.get("outcomePrices")
            or data.get("prices")
            or data.get("outcome_prices")
        )
        outcome_prices = self._coerce_prices_sequence(
            outcome_prices_raw, market_id=market_id
        )

        if tokens_data and outcomes_data and outcome_prices:
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

            if (
                price is None
                and isinstance(outcome_prices, (list, tuple))
                and len(outcome_prices) > idx
            ):
                price = outcome_prices[idx]
            else:
                print(outcome_prices_raw)
                raise ValueError("Missing price")

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

    def _coerce_sequence(
        self,
        value: Any,
        *,
        label: str,
        market_id: Any,
    ) -> List[Any]:
        """Convert list-like values (or list strings) into concrete lists."""

        if value is None:
            return []

        if isinstance(value, str):
            try:
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError) as exc:
                raise ValueError(
                    f"Market {market_id} {label} payload could not be parsed as list: {value}"
                ) from exc

        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
            return list(value)

        raise TypeError(
            f"Market {market_id} {label} payload must be list-like; got {type(value).__name__}"
        )

    def _coerce_prices_sequence(
        self,
        value: Any,
        *,
        market_id: Any,
    ) -> Optional[List[Any]]:
        """Coerce price arrays (or stringified arrays) into lists."""

        if value is None:
            return None

        prices = self._coerce_sequence(value, label="prices", market_id=market_id)
        return prices
