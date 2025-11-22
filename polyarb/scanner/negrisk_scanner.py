"""
Scanner for NegRisk market rebalancing opportunities.
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from polyarb.scanner.base_scanner import BaseScanner, ScanResult
from polyarb.scanner.enhanced_opportunity import (
    EnhancedOpportunity,
    OpportunityClass,
    RiskLevel,
    Leg
)
from polyarb.data.models import PriceType


class NegRiskScanner(BaseScanner):
    """
    Scans for within-market rebalancing opportunities in NegRisk markets.
    
    NegRisk markets have mutually exclusive and exhaustive outcomes.
    When sum of YES prices < 1, buying all YES positions guarantees profit.
    """
    
    async def scan(
        self,
        markets: List[Dict[str, Any]],
        price_type: PriceType = None,
        **kwargs
    ) -> ScanResult:
        """
        Scan NegRisk markets for rebalancing opportunities.
        
        Args:
            markets: List of market dictionaries
            price_type: Price type to use
            **kwargs: Additional parameters
            
        Returns:
            ScanResult with opportunities
        """
        start_time = datetime.utcnow()
        price_type = price_type or self.price_type
        opportunities = []
        
        # Group markets by neg_risk_id
        negrisk_groups = self._group_negrisk_markets(markets)
        
        for neg_risk_id, group_markets in negrisk_groups.items():
            opp = await self._check_negrisk_group(
                neg_risk_id,
                group_markets,
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
    
    def _group_negrisk_markets(
        self,
        markets: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group markets by neg_risk_id.
        
        Args:
            markets: List of all markets
            
        Returns:
            Dictionary mapping neg_risk_id to list of markets
        """
        groups = {}
        
        for market in markets:
            if market.get("is_neg_risk") and market.get("neg_risk_id"):
                neg_risk_id = market["neg_risk_id"]
                if neg_risk_id not in groups:
                    groups[neg_risk_id] = []
                groups[neg_risk_id].append(market)
        
        # Filter to groups with multiple markets (multi-outcome)
        return {k: v for k, v in groups.items() if len(v) >= 2}
    
    async def _check_negrisk_group(
        self,
        neg_risk_id: str,
        markets: List[Dict[str, Any]],
        price_type: PriceType
    ) -> Optional[EnhancedOpportunity]:
        """
        Check a NegRisk group for rebalancing opportunities.
        
        Args:
            neg_risk_id: NegRisk ID
            markets: List of markets in this NegRisk group
            price_type: Price type to use
            
        Returns:
            EnhancedOpportunity or None
        """
        legs = []
        total_cost = 0.0
        
        for market in markets:
            outcomes = market.get("outcomes", [])
            
            if not outcomes:
                continue
            
            # For NegRisk, we buy YES on each outcome
            # (each outcome is mutually exclusive, exactly one will resolve TRUE)
            outcome = outcomes[0]  # Primary outcome for this market
            yes_token_id = outcome.get("yes_token_id")
            
            if not yes_token_id:
                continue
            
            # Get YES price
            yes_price = await self.price_accessor.get_price(
                yes_token_id,
                price_type,
                side="buy"
            )
            
            if yes_price is None:
                continue
            
            # Create leg
            leg = Leg(
                token_id=yes_token_id,
                side="YES",
                outcome_label=outcome.get("label", ""),
                market_id=market.get("id"),
                market_question=market.get("question", ""),
                price=yes_price,
                price_type=price_type.value,
            )
            
            # Fetch spread data
            spread_data = await self.price_accessor.clob_client.fetch_spread(yes_token_id)
            if spread_data:
                leg.spread_bps = spread_data.get("spread_bps")
                leg.depth = spread_data.get("best_ask_size", 0)
            
            legs.append(leg)
            total_cost += yes_price
        
        if len(legs) < 2:
            return None
        
        # Check for arbitrage (sum of YES prices < 1)
        if total_cost >= self.max_total_price_threshold:
            return None
        
        # Calculate profit metrics
        metrics = self.calculate_profit_metrics(
            total_cost=total_cost,
            worst_case_payoff=1.0,  # Exactly one outcome resolves TRUE
            best_case_payoff=1.0
        )
        
        if not self.is_opportunity_valid(metrics["profit_percentage"], total_cost):
            return None
        
        # Apply spread adjustment
        adjusted_cost = self.apply_spread_adjustment(total_cost, legs)
        adjusted_profit = 1.0 - adjusted_cost
        adjusted_profit_pct = (adjusted_profit / adjusted_cost * 100) if adjusted_cost > 0 else 0
        
        # Estimate liquidity
        liquidity_score = self.estimate_liquidity_score(legs)
        max_size = min(leg.depth for leg in legs if leg.depth) if any(leg.depth for leg in legs) else None
        
        # Get event IDs
        event_ids = list(set(m.get("event_id") for m in markets if m.get("event_id")))
        market_ids = [m.get("id") for m in markets]
        
        # Create opportunity
        opportunity = EnhancedOpportunity(
            id=str(uuid.uuid4()),
            opportunity_class=OpportunityClass.NEGRISK_REBALANCING,
            name=f"NegRisk Rebalancing: {len(legs)} outcomes",
            description=(
                f"Buy YES on all {len(legs)} mutually exclusive outcomes "
                f"for guaranteed profit. Total cost: {total_cost:.4f}"
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
            event_ids=event_ids,
            is_pure_arbitrage=True,
            tags=["negrisk", f"neg_risk_id:{neg_risk_id}"],
        )
        
        return opportunity
