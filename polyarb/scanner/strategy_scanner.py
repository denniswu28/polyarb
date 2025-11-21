"""
Scanner for strategy-based opportunities (all_no, balanced, custom).
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
from polyarb.strategies.base import Strategy, StrategyMethod, StrategyType


class StrategyScanner(BaseScanner):
    """
    Scans strategies from registry for profitability.
    
    Evaluates strategy templates (all_no, balanced) with current market prices
    to identify arbitrage opportunities.
    """
    
    async def scan_strategies(
        self,
        strategies: List[Strategy],
        price_type: PriceType = None,
        **kwargs
    ) -> ScanResult:
        """
        Scan a list of strategies for opportunities.
        
        Args:
            strategies: List of Strategy objects
            price_type: Price type to use
            **kwargs: Additional parameters
            
        Returns:
            ScanResult with opportunities
        """
        start_time = datetime.utcnow()
        price_type = price_type or self.price_type
        opportunities = []
        
        for strategy in strategies:
            opp = await self._evaluate_strategy(strategy, price_type)
            if opp:
                opportunities.append(opp)
        
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        return ScanResult(
            opportunities=opportunities,
            scan_duration_ms=duration_ms,
            markets_scanned=len(strategies),
            timestamp=end_time,
            price_type=price_type
        )
    
    async def _evaluate_strategy(
        self,
        strategy: Strategy,
        price_type: PriceType
    ) -> Optional[EnhancedOpportunity]:
        """
        Evaluate a strategy for profitability.
        
        Args:
            strategy: Strategy to evaluate
            price_type: Price type to use
            
        Returns:
            EnhancedOpportunity or None
        """
        if strategy.method == StrategyMethod.ALL_NO:
            return await self._evaluate_all_no_strategy(strategy, price_type)
        elif strategy.method == StrategyMethod.BALANCED:
            return await self._evaluate_balanced_strategy(strategy, price_type)
        else:
            return await self._evaluate_custom_strategy(strategy, price_type)
    
    async def _evaluate_all_no_strategy(
        self,
        strategy: Strategy,
        price_type: PriceType
    ) -> Optional[EnhancedOpportunity]:
        """
        Evaluate an 'all_no' strategy.
        
        Buy NO on mutually exclusive outcomes. One outcome occurs,
        so n-1 positions win, 1 position loses.
        """
        legs = []
        total_cost = 0.0
        
        for position in strategy.positions:
            # Get NO price
            price = await self.price_accessor.get_price(
                position.token_id,
                price_type,
                side="buy"
            )
            
            if price is None:
                return None  # Can't evaluate if any price is missing
            
            # Create leg
            leg = Leg(
                token_id=position.token_id,
                side=position.side,
                outcome_label=position.outcome_label,
                market_id=position.market_id,
                market_question="",  # Could fetch from DB if needed
                price=price,
                price_type=price_type.value,
            )
            
            # Fetch spread data
            spread_data = await self.price_accessor.clob_client.fetch_spread(position.token_id)
            if spread_data:
                leg.spread_bps = spread_data.get("spread_bps")
                leg.depth = spread_data.get("best_ask_size", 0)
            
            legs.append(leg)
            total_cost += price
        
        # Calculate payoff
        n = len(legs)
        worst_case_payoff = float(n - 1)  # n-1 positions win
        
        # Calculate profit metrics
        metrics = self.calculate_profit_metrics(
            total_cost=total_cost,
            worst_case_payoff=worst_case_payoff,
            best_case_payoff=worst_case_payoff
        )
        
        if not self.is_opportunity_valid(metrics["profit_percentage"], total_cost):
            return None
        
        # Apply spread adjustment
        adjusted_cost = self.apply_spread_adjustment(total_cost, legs)
        adjusted_profit = worst_case_payoff - adjusted_cost
        adjusted_profit_pct = (adjusted_profit / adjusted_cost * 100) if adjusted_cost > 0 else 0
        
        # Estimate liquidity
        liquidity_score = self.estimate_liquidity_score(legs)
        max_size = min(leg.depth for leg in legs if leg.depth) if any(leg.depth for leg in legs) else None
        
        # Determine risk level
        risk_level = (
            RiskLevel.LOW if strategy.strategy_type == StrategyType.PURE_LOGICAL
            else RiskLevel.MEDIUM
        )
        
        # Create opportunity
        opportunity = EnhancedOpportunity(
            id=str(uuid.uuid4()),
            opportunity_class=OpportunityClass.TEMPLATE_BASED,
            strategy_id=strategy.id,
            name=strategy.name,
            description=strategy.subtitle or f"all_no strategy with {n} positions",
            legs=legs,
            total_cost=total_cost,
            worst_case_payoff=worst_case_payoff,
            best_case_payoff=worst_case_payoff,
            expected_profit=metrics["expected_profit"],
            profit_percentage=metrics["profit_percentage"],
            adjusted_cost=adjusted_cost,
            adjusted_profit=adjusted_profit,
            adjusted_profit_percentage=adjusted_profit_pct,
            risk_level=risk_level,
            max_size=max_size,
            liquidity_score=liquidity_score,
            market_ids=strategy.get_markets(),
            event_ids=strategy.get_events(),
            is_pure_arbitrage=(strategy.strategy_type == StrategyType.PURE_LOGICAL),
            tags=strategy.tags + ["all_no"],
            topic=strategy.topic,
        )
        
        return opportunity
    
    async def _evaluate_balanced_strategy(
        self,
        strategy: Strategy,
        price_type: PriceType
    ) -> Optional[EnhancedOpportunity]:
        """
        Evaluate a 'balanced' strategy.
        
        Two complementary baskets that cover outcome space.
        """
        legs = []
        total_cost = 0.0
        
        # Evaluate all positions (side A + side B)
        all_positions = strategy.side_a_positions + strategy.side_b_positions
        
        for position in all_positions:
            # Get price
            price = await self.price_accessor.get_price(
                position.token_id,
                price_type,
                side="buy"
            )
            
            if price is None:
                return None
            
            # Create leg
            leg = Leg(
                token_id=position.token_id,
                side=position.side,
                outcome_label=position.outcome_label,
                market_id=position.market_id,
                market_question="",
                price=price,
                price_type=price_type.value,
            )
            
            # Fetch spread data
            spread_data = await self.price_accessor.clob_client.fetch_spread(position.token_id)
            if spread_data:
                leg.spread_bps = spread_data.get("spread_bps")
                leg.depth = spread_data.get("best_ask_size", 0)
            
            legs.append(leg)
            total_cost += price
        
        # Use logical spec if available
        if strategy.logical_spec:
            worst_case_payoff = strategy.logical_spec.worst_case_payoff
            best_case_payoff = strategy.logical_spec.best_case_payoff
        else:
            # Default assumption: at least one position wins
            worst_case_payoff = 1.0
            best_case_payoff = 1.0
        
        # Calculate profit metrics
        metrics = self.calculate_profit_metrics(
            total_cost=total_cost,
            worst_case_payoff=worst_case_payoff,
            best_case_payoff=best_case_payoff
        )
        
        if not self.is_opportunity_valid(metrics["profit_percentage"], total_cost):
            return None
        
        # Apply spread adjustment
        adjusted_cost = self.apply_spread_adjustment(total_cost, legs)
        adjusted_profit = worst_case_payoff - adjusted_cost
        adjusted_profit_pct = (adjusted_profit / adjusted_cost * 100) if adjusted_cost > 0 else 0
        
        # Estimate liquidity
        liquidity_score = self.estimate_liquidity_score(legs)
        max_size = min(leg.depth for leg in legs if leg.depth) if any(leg.depth for leg in legs) else None
        
        # Determine risk level
        risk_level = (
            RiskLevel.LOW if strategy.strategy_type == StrategyType.PURE_LOGICAL
            else RiskLevel.MEDIUM
        )
        
        # Create opportunity
        opportunity = EnhancedOpportunity(
            id=str(uuid.uuid4()),
            opportunity_class=OpportunityClass.TEMPLATE_BASED,
            strategy_id=strategy.id,
            name=strategy.name,
            description=strategy.subtitle or f"balanced strategy with {len(legs)} positions",
            legs=legs,
            total_cost=total_cost,
            worst_case_payoff=worst_case_payoff,
            best_case_payoff=best_case_payoff,
            expected_profit=metrics["expected_profit"],
            profit_percentage=metrics["profit_percentage"],
            adjusted_cost=adjusted_cost,
            adjusted_profit=adjusted_profit,
            adjusted_profit_percentage=adjusted_profit_pct,
            risk_level=risk_level,
            max_size=max_size,
            liquidity_score=liquidity_score,
            market_ids=strategy.get_markets(),
            event_ids=strategy.get_events(),
            is_pure_arbitrage=(strategy.strategy_type == StrategyType.PURE_LOGICAL),
            tags=strategy.tags + ["balanced"],
            topic=strategy.topic,
        )
        
        return opportunity
    
    async def _evaluate_custom_strategy(
        self,
        strategy: Strategy,
        price_type: PriceType
    ) -> Optional[EnhancedOpportunity]:
        """
        Evaluate a custom strategy.
        
        Similar to balanced but with custom logic.
        """
        # For now, treat same as balanced
        return await self._evaluate_balanced_strategy(strategy, price_type)
