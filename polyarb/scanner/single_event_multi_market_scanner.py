"""
Scanner for single-event, multi-market arbitrage opportunities.

This scanner looks for events that contain several binary markets representing
mutually exclusive options plus a catch-all "other" option. When the YES prices
for all such markets sum to less than 1, buying every YES guarantees a profit
because at least one market must resolve to YES.
"""

import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional
from datetime import datetime

from polyarb.scanner.base_scanner import BaseScanner, ScanResult
from polyarb.scanner.enhanced_opportunity import (
    EnhancedOpportunity,
    OpportunityClass,
    RiskLevel,
    Leg,
)
from polyarb.data.models import PriceType


class SingleEventMultiMarketScanner(BaseScanner):
    """
    Scans events for arbitrage across multiple markets within the same event.

    Focuses on events that include an "other/another" style option which makes
    the set of markets exhaustive. The scanner buys YES on every market and
    checks if the total cost is below the guaranteed payoff of 1.0.
    """

    def __init__(
        self,
        price_accessor,
        min_profit_threshold: float = 0.5,
        max_total_price_threshold: float = 0.98,
        price_type: PriceType = PriceType.ASK,
        other_keywords: Optional[List[str]] = None,
    ):
        super().__init__(
            price_accessor=price_accessor,
            min_profit_threshold=min_profit_threshold,
            max_total_price_threshold=max_total_price_threshold,
            price_type=price_type,
        )
        self.other_keywords = [
            "other",
            "another",
            "any other",
            "others",
            "anyone else",
            "someone else",
        ] if other_keywords is None else other_keywords

    async def scan(
        self,
        markets: List[Dict[str, Any]],
        price_type: PriceType = None,
        **kwargs,
    ) -> ScanResult:
        """
        Scan markets grouped by event to find multi-market arbitrage.

        Args:
            markets: List of market dictionaries
            price_type: Price type to use (defaults to self.price_type)

        Returns:
            ScanResult with discovered opportunities
        """
        start_time = datetime.utcnow()
        price_type = price_type or self.price_type
        opportunities: List[EnhancedOpportunity] = []

        event_groups = self._group_markets_by_event(markets)

        for event_id, event_markets in event_groups.items():
            opp = await self._check_event_group(event_id, event_markets, price_type)
            if opp:
                opportunities.append(opp)

        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        return ScanResult(
            opportunities=opportunities,
            scan_duration_ms=duration_ms,
            markets_scanned=len(markets),
            timestamp=end_time,
            price_type=price_type,
        )

    def _group_markets_by_event(
        self, markets: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group markets by their event_id."""
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for market in markets:
            event_id = market.get("event_id")
            if event_id:
                groups[event_id].append(market)
        return groups

    async def _check_event_group(
        self,
        event_id: str,
        markets: List[Dict[str, Any]],
        price_type: PriceType,
    ) -> Optional[EnhancedOpportunity]:
        """
        Evaluate a group of markets within a single event.

        Requires the event to contain an "other" style market to ensure
        coverage of the outcome space.
        """
        if len(markets) < 2:
            return None

        if not any(self._is_other_market(market) for market in markets):
            return None

        legs: List[Leg] = []
        total_cost = 0.0
        market_ids: List[str] = []

        for market in markets:
            primary_outcome = self._select_primary_outcome(market)
            if not primary_outcome:
                continue

            yes_token_id = primary_outcome.get("yes_token_id")
            if not yes_token_id:
                continue

            yes_price = await self.price_accessor.get_price(
                yes_token_id,
                price_type,
                side="buy",
            )
            if yes_price is None:
                continue

            leg = Leg(
                token_id=yes_token_id,
                side="YES",
                outcome_label=primary_outcome.get("label", ""),
                market_id=market.get("id"),
                market_question=market.get("question", ""),
                price=yes_price,
                price_type=price_type.value,
            )

            spread_data = await self.price_accessor.clob_client.fetch_spread(
                yes_token_id
            )
            if spread_data:
                leg.spread_bps = spread_data.get("spread_bps")
                leg.depth = spread_data.get("best_ask_size", 0) + spread_data.get(
                    "best_bid_size", 0
                )

            legs.append(leg)
            total_cost += yes_price
            market_ids.append(market.get("id"))

        if len(legs) < 2:
            return None

        if total_cost >= self.max_total_price_threshold:
            return None

        metrics = self.calculate_profit_metrics(
            total_cost=total_cost,
            worst_case_payoff=1.0,
            best_case_payoff=1.0,
        )

        if not self.is_opportunity_valid(metrics["profit_percentage"], total_cost):
            return None

        adjusted_cost = self.apply_spread_adjustment(total_cost, legs)
        adjusted_profit = 1.0 - adjusted_cost
        adjusted_profit_pct = (
            (adjusted_profit / adjusted_cost * 100) if adjusted_cost > 0 else 0
        )

        liquidity_score = self.estimate_liquidity_score(legs)
        max_size = (
            min(leg.depth for leg in legs if leg.depth)
            if any(leg.depth for leg in legs)
            else None
        )

        opportunity = EnhancedOpportunity(
            id=str(uuid.uuid4()),
            opportunity_class=OpportunityClass.SINGLE_EVENT_MULTI_MARKET,
            name=f"Event coverage arb ({len(legs)} markets)",
            description=(
                "Buy YES across all markets in the event, including the "
                "'other' option, for guaranteed coverage."
            ),
            legs=legs,
            total_cost=total_cost,
            worst_case_payoff=1.0,
            best_case_payoff=1.0,
            expected_profit=metrics["expected_profit"],
            profit_percentage=metrics["profit_percentage"],
            adjusted_cost=adjusted_cost,
            adjusted_profit=adjusted_profit,
            adjusted_profit_percentage=adjusted_profit_pct,
            risk_level=RiskLevel.LOW,
            max_size=max_size,
            liquidity_score=liquidity_score,
            market_ids=market_ids,
            event_ids=[event_id],
            is_pure_arbitrage=True,
            tags=["multi_market_event", "other_option"],
        )

        return opportunity

    def _select_primary_outcome(self, market: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select the outcome representing the YES side for this market."""
        outcomes = market.get("outcomes", []) or []
        if not outcomes:
            return None

        yes_labels = {"yes", "true"}
        for outcome in outcomes:
            label = outcome.get("label", "").lower()
            if label in yes_labels:
                return outcome

        return outcomes[0]

    def _is_other_market(self, market: Dict[str, Any]) -> bool:
        """Check if a market represents an "other" catch-all option."""
        text_parts: List[str] = []
        question = market.get("question")
        if question:
            text_parts.append(question)

        for outcome in market.get("outcomes", []) or []:
            label = outcome.get("label")
            if label:
                text_parts.append(label)

        combined_text = " ".join(text_parts).lower()
        return any(keyword in combined_text for keyword in self.other_keywords)
