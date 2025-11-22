"""
Risk management and position limits.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from decimal import Decimal

from polyarb.scanner.enhanced_opportunity import EnhancedOpportunity, RiskLevel


@dataclass
class RiskLimits:
    """Risk limits configuration."""
    
    # Notional limits
    max_total_notional: float = 10000.0  # Max total exposure
    max_per_strategy_notional: float = 2000.0
    max_per_market_notional: float = 1000.0
    max_per_entity_notional: float = 500.0  # Per candidate/team
    max_per_topic_notional: float = 3000.0
    
    # Position limits
    max_positions: int = 50
    max_positions_per_market: int = 5
    
    # Quality limits
    min_profit_threshold: float = 0.5  # 0.5% minimum
    max_rule_risk_exposure: float = 2000.0  # Max exposure to high rule-risk
    
    # Execution limits
    max_slippage_tolerance: float = 50  # basis points
    min_liquidity_score: float = 0.3  # 0-1 scale


class RiskManager:
    """
    Manages risk limits and position tracking.
    """
    
    def __init__(self, limits: Optional[RiskLimits] = None):
        """
        Initialize risk manager.
        
        Args:
            limits: Risk limits configuration
        """
        self.limits = limits or RiskLimits()
        
        # Current positions tracking
        self.positions: Dict[str, Dict] = {}  # token_id -> position info
        self.strategy_exposures: Dict[str, float] = {}
        self.market_exposures: Dict[str, float] = {}
        self.topic_exposures: Dict[str, float] = {}
        
        self.total_notional = 0.0
        self.total_rule_risk_exposure = 0.0
    
    def check_opportunity(
        self,
        opportunity: EnhancedOpportunity,
        proposed_size: float
    ) -> tuple[bool, List[str]]:
        """
        Check if opportunity passes risk checks.
        
        Args:
            opportunity: Opportunity to check
            proposed_size: Proposed position size
            
        Returns:
            Tuple of (passed, list of violation messages)
        """
        violations = []
        
        # Check profit threshold
        if opportunity.profit_percentage < self.limits.min_profit_threshold:
            violations.append(
                f"Profit {opportunity.profit_percentage:.2f}% below threshold "
                f"{self.limits.min_profit_threshold:.2f}%"
            )
        
        # Check total notional
        proposed_total = self.total_notional + (opportunity.total_cost * proposed_size)
        if proposed_total > self.limits.max_total_notional:
            violations.append(
                f"Would exceed max total notional: {proposed_total:.2f} > "
                f"{self.limits.max_total_notional:.2f}"
            )
        
        # Check per-strategy limit
        if opportunity.strategy_id:
            current_strategy_exposure = self.strategy_exposures.get(
                opportunity.strategy_id, 0.0
            )
            proposed_strategy_exposure = current_strategy_exposure + (
                opportunity.total_cost * proposed_size
            )
            if proposed_strategy_exposure > self.limits.max_per_strategy_notional:
                violations.append(
                    f"Would exceed per-strategy limit for {opportunity.strategy_id}"
                )
        
        # Check per-market limits
        for market_id in opportunity.market_ids:
            current_market_exposure = self.market_exposures.get(market_id, 0.0)
            proposed_market_exposure = current_market_exposure + (
                opportunity.total_cost * proposed_size / len(opportunity.market_ids)
            )
            if proposed_market_exposure > self.limits.max_per_market_notional:
                violations.append(f"Would exceed per-market limit for {market_id}")
        
        # Check topic limit
        if opportunity.topic:
            current_topic_exposure = self.topic_exposures.get(opportunity.topic, 0.0)
            proposed_topic_exposure = current_topic_exposure + (
                opportunity.total_cost * proposed_size
            )
            if proposed_topic_exposure > self.limits.max_per_topic_notional:
                violations.append(
                    f"Would exceed per-topic limit for {opportunity.topic}"
                )
        
        # Check rule risk
        if opportunity.risk_level == RiskLevel.HIGH:
            proposed_rule_risk = self.total_rule_risk_exposure + (
                opportunity.total_cost * proposed_size
            )
            if proposed_rule_risk > self.limits.max_rule_risk_exposure:
                violations.append("Would exceed rule risk exposure limit")
        
        # Check liquidity
        if opportunity.liquidity_score and opportunity.liquidity_score < self.limits.min_liquidity_score:
            violations.append(
                f"Liquidity score {opportunity.liquidity_score:.2f} below minimum "
                f"{self.limits.min_liquidity_score:.2f}"
            )
        
        # Check max positions
        if len(self.positions) >= self.limits.max_positions:
            violations.append(f"Already at max positions limit: {self.limits.max_positions}")
        
        passed = len(violations) == 0
        return passed, violations
    
    def add_position(
        self,
        opportunity: EnhancedOpportunity,
        size: float,
        execution_id: str
    ) -> None:
        """
        Add a position to tracking.
        
        Args:
            opportunity: Executed opportunity
            size: Position size
            execution_id: Execution ID for tracking
        """
        position_value = opportunity.total_cost * size
        
        # Track per leg
        for leg in opportunity.legs:
            self.positions[leg.token_id] = {
                "opportunity_id": opportunity.id,
                "execution_id": execution_id,
                "size": size,
                "cost": leg.price * size,
                "market_id": leg.market_id,
                "side": leg.side,
            }
        
        # Update exposures
        self.total_notional += position_value
        
        if opportunity.strategy_id:
            self.strategy_exposures[opportunity.strategy_id] = (
                self.strategy_exposures.get(opportunity.strategy_id, 0.0) + position_value
            )
        
        for market_id in opportunity.market_ids:
            self.market_exposures[market_id] = (
                self.market_exposures.get(market_id, 0.0) + 
                position_value / len(opportunity.market_ids)
            )
        
        if opportunity.topic:
            self.topic_exposures[opportunity.topic] = (
                self.topic_exposures.get(opportunity.topic, 0.0) + position_value
            )
        
        if opportunity.risk_level == RiskLevel.HIGH:
            self.total_rule_risk_exposure += position_value
    
    def remove_position(self, token_id: str) -> None:
        """
        Remove a position (e.g., after settlement).
        
        Args:
            token_id: Token ID to remove
        """
        if token_id in self.positions:
            position = self.positions[token_id]
            
            # Update exposures
            self.total_notional -= position["cost"]
            
            # Clean up tracking
            del self.positions[token_id]
    
    def get_exposure_summary(self) -> Dict[str, any]:
        """
        Get summary of current exposures.
        
        Returns:
            Dictionary with exposure metrics
        """
        return {
            "total_notional": self.total_notional,
            "total_positions": len(self.positions),
            "rule_risk_exposure": self.total_rule_risk_exposure,
            "strategy_exposures": dict(self.strategy_exposures),
            "market_exposures": dict(self.market_exposures),
            "topic_exposures": dict(self.topic_exposures),
            "utilization": {
                "total_notional": self.total_notional / self.limits.max_total_notional,
                "positions": len(self.positions) / self.limits.max_positions,
                "rule_risk": self.total_rule_risk_exposure / self.limits.max_rule_risk_exposure,
            }
        }
    
    def suggest_position_size(
        self,
        opportunity: EnhancedOpportunity,
        max_size: Optional[float] = None
    ) -> float:
        """
        Suggest appropriate position size given risk limits.
        
        Args:
            opportunity: Opportunity to size
            max_size: Maximum size from liquidity constraints
            
        Returns:
            Suggested position size
        """
        # Start with max size from liquidity
        size = max_size if max_size else 100.0
        
        # Constrain by total notional available
        available_notional = self.limits.max_total_notional - self.total_notional
        max_size_from_total = available_notional / opportunity.total_cost
        size = min(size, max_size_from_total)
        
        # Constrain by per-strategy limit
        if opportunity.strategy_id:
            available_strategy = (
                self.limits.max_per_strategy_notional - 
                self.strategy_exposures.get(opportunity.strategy_id, 0.0)
            )
            max_size_from_strategy = available_strategy / opportunity.total_cost
            size = min(size, max_size_from_strategy)
        
        # Constrain by per-market limits
        for market_id in opportunity.market_ids:
            available_market = (
                self.limits.max_per_market_notional - 
                self.market_exposures.get(market_id, 0.0)
            )
            max_size_from_market = available_market / (
                opportunity.total_cost / len(opportunity.market_ids)
            )
            size = min(size, max_size_from_market)
        
        return max(0.0, size)
