"""
Scanner for single-condition YES/NO arbitrage opportunities.
"""

import uuid
from typing import List, Dict, Any
from datetime import datetime

from polyarb.scanner.base_scanner import BaseScanner, ScanResult
from polyarb.scanner.enhanced_opportunity import (
    EnhancedOpportunity, 
    OpportunityClass,
    RiskLevel,
    Leg
)
from polyarb.data.models import PriceType


class SingleConditionScanner(BaseScanner):
    """
    Scans for single-condition YES/NO arbitrage (Dutch-book).
    
    When price(YES) + price(NO) < 1, buying both guarantees profit.
    """
    
    async def scan(
        self,
        markets: List[Dict[str, Any]],
        price_type: PriceType = None,
        **kwargs
    ) -> ScanResult:
        """
        Scan markets for single-condition arbitrage.
        
        Args:
            markets: List of market dictionaries with outcomes
            price_type: Price type to use (defaults to self.price_type)
            **kwargs: Additional parameters
            
        Returns:
            ScanResult with opportunities
        """
        start_time = datetime.utcnow()
        price_type = price_type or self.price_type
        opportunities = []
        
        for market in markets:
            outcomes = market.get("outcomes", [])
            
            # For single-condition markets (YES/NO binary)
            if len(outcomes) == 2:
                opp = await self._check_binary_market(
                    market, 
                    outcomes,
                    price_type
                )
                if opp:
                    opportunities.append(opp)
        
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        return ScanResult(
            opportunities=opportunities,
            scan_duration_ms=duration_ms,
            markets_scanned=len(markets),
            timestamp=end_time,
            price_type=price_type
        )
    
    async def _check_binary_market(
        self,
        market: Dict[str, Any],
        outcomes: List[Dict[str, Any]],
        price_type: PriceType
    ) -> Optional[EnhancedOpportunity]:
        """
        Check a binary market for YES/NO arbitrage.
        
        Args:
            market: Market dictionary
            outcomes: List of outcomes (should be 2)
            price_type: Price type to use
            
        Returns:
            EnhancedOpportunity or None
        """
        if len(outcomes) != 2:
            return None
        
        # Get YES and NO outcomes
        yes_outcome = outcomes[0] if outcomes[0].get("label", "").lower() in ["yes", "true"] else outcomes[1]
        no_outcome = outcomes[1] if yes_outcome == outcomes[0] else outcomes[0]
        
        # Get token IDs
        yes_token_id = yes_outcome.get("yes_token_id")
        no_token_id = no_outcome.get("no_token_id")
        
        if not yes_token_id or not no_token_id:
            return None
        
        price_candidates: list[tuple[PriceType, float, float]] = []

        # Respect requested price type when it explicitly demands bid/ask
        candidate_types = [PriceType.ASK, PriceType.BID]
        if price_type in (PriceType.ASK, PriceType.BID):
            candidate_types = [price_type]

        if PriceType.ASK in candidate_types:
            # Fetch ASK prices (cost to buy both sides)
            yes_ask = await self.price_accessor.get_price(
                yes_token_id,
                PriceType.ASK,
                side="buy"
            )

            no_ask = await self.price_accessor.get_price(
                no_token_id,
                PriceType.ASK,
                side="buy"
            )

            if yes_ask is not None and no_ask is not None:
                price_candidates.append((PriceType.ASK, yes_ask, no_ask))

        if PriceType.BID in candidate_types:
            # Fetch BID prices (potential to sell both sides)
            yes_bid = await self.price_accessor.get_price(
                yes_token_id,
                PriceType.BID,
                side="sell"
            )

            no_bid = await self.price_accessor.get_price(
                no_token_id,
                PriceType.BID,
                side="sell"
            )

            if yes_bid is not None and no_bid is not None:
                price_candidates.append((PriceType.BID, yes_bid, no_bid))

        # Only consider opportunities that use consistent bid/ask prices
        valid_candidates: list[tuple[PriceType, float, float, float]] = [
            (ptype, y_price, n_price, y_price + n_price)
            for ptype, y_price, n_price in price_candidates
            if (y_price + n_price) < self.max_total_price_threshold
        ]

        if not valid_candidates:
            return None

        # Choose the cheapest viable pairing (ask or bid)
        selected_type, yes_price, no_price, total_cost = min(
            valid_candidates,
            key=lambda candidate: candidate[3]
        )
        
        # Calculate profit metrics
        metrics = self.calculate_profit_metrics(
            total_cost=total_cost,
            worst_case_payoff=1.0,  # Always pays 1
            best_case_payoff=1.0
        )
        
        if not self.is_opportunity_valid(metrics["profit_percentage"], total_cost):
            return None
        
        # Create legs
        legs = [
            Leg(
                token_id=yes_token_id,
                side="YES",
                outcome_label=yes_outcome.get("label", "Yes"),
                market_id=market.get("id"),
                market_question=market.get("question", ""),
                price=yes_price,
                price_type=selected_type.value,
            ),
            Leg(
                token_id=no_token_id,
                side="NO",
                outcome_label=no_outcome.get("label", "No"),
                market_id=market.get("id"),
                market_question=market.get("question", ""),
                price=no_price,
                price_type=selected_type.value,
            )
        ]
        
        # Fetch spread data for adjustment
        for leg in legs:
            spread_data = await self.price_accessor.clob_client.fetch_spread(leg.token_id)
            if spread_data:
                leg.spread_bps = spread_data.get("spread_bps")
                leg.depth = spread_data.get("best_ask_size", 0) + spread_data.get("best_bid_size", 0)
        
        # Apply spread adjustment
        adjusted_cost = self.apply_spread_adjustment(total_cost, legs)
        adjusted_profit = 1.0 - adjusted_cost
        adjusted_profit_pct = (adjusted_profit / adjusted_cost * 100) if adjusted_cost > 0 else 0
        
        # Estimate liquidity
        liquidity_score = self.estimate_liquidity_score(legs)
        max_size = min(leg.depth for leg in legs if leg.depth) if any(leg.depth for leg in legs) else None
        
        # Create opportunity
        opportunity = EnhancedOpportunity(
            id=str(uuid.uuid4()),
            opportunity_class=OpportunityClass.SINGLE_CONDITION,
            name=f"YES/NO Arbitrage: {market.get('question', '')[:50]}",
            description=(
                f"Use {selected_type.value.upper()} prices: YES at {yes_price:.4f} "
                f"and NO at {no_price:.4f} for guaranteed profit"
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
            market_ids=[market.get("id")],
            event_ids=[market.get("event_id")] if market.get("event_id") else [],
            is_pure_arbitrage=True,
            topic=market.get("topic"),
        )
        
        return opportunity
