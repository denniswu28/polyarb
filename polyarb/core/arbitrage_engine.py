"""
Arbitrage detection engine.

This module provides the core arbitrage detection logic for finding opportunities
within and across prediction market platforms.
"""

from typing import List, Dict, Optional, Set
from itertools import combinations

from polyarb.platforms.base import PlatformInterface, Market
from polyarb.core.opportunity import ArbitrageOpportunity, OpportunityType


class ArbitrageEngine:
    """
    Engine for detecting arbitrage opportunities across prediction markets.
    """
    
    def __init__(
        self,
        platforms: Optional[List[PlatformInterface]] = None,
        min_profit_threshold: float = 1.0,
        max_total_price_threshold: float = 0.98
    ):
        """
        Initialize the arbitrage engine.
        
        Args:
            platforms: List of platform interfaces to monitor
            min_profit_threshold: Minimum profit percentage to report (default 1%)
            max_total_price_threshold: Maximum total price for intra-platform arb (default 0.98)
        """
        self.platforms = platforms or []
        self.min_profit_threshold = min_profit_threshold
        self.max_total_price_threshold = max_total_price_threshold
    
    def add_platform(self, platform: PlatformInterface) -> None:
        """Add a platform to monitor."""
        if platform not in self.platforms:
            self.platforms.append(platform)
    
    def remove_platform(self, platform: PlatformInterface) -> None:
        """Remove a platform from monitoring."""
        if platform in self.platforms:
            self.platforms.remove(platform)
    
    def find_opportunities(self) -> List[ArbitrageOpportunity]:
        """
        Find all arbitrage opportunities across registered platforms.
        
        Returns:
            List of ArbitrageOpportunity objects
        """
        opportunities = []
        
        # Find intra-platform opportunities for each platform
        for platform in self.platforms:
            intra_opps = self.find_intra_platform_opportunities(platform)
            opportunities.extend(intra_opps)
        
        # Find cross-platform opportunities
        if len(self.platforms) > 1:
            cross_opps = self.find_cross_platform_opportunities()
            opportunities.extend(cross_opps)
        
        # Filter by profit threshold
        opportunities = [
            opp for opp in opportunities 
            if opp.is_profitable(self.min_profit_threshold)
        ]
        
        return opportunities
    
    def find_intra_platform_opportunities(
        self, 
        platform: PlatformInterface
    ) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities within a single platform.
        
        This looks for markets where the sum of outcome prices is less than 1,
        allowing for risk-free profit by buying all outcomes.
        
        Args:
            platform: Platform to analyze
            
        Returns:
            List of intra-platform arbitrage opportunities
        """
        opportunities = []
        
        try:
            markets = platform.get_markets(limit=100)
            
            for market in markets:
                if not market.prices or len(market.prices) < 2:
                    continue
                
                # Calculate total price of all outcomes
                total_price = sum(market.prices.values())
                
                # If total price < 1, there's an arbitrage opportunity
                if total_price < self.max_total_price_threshold:
                    profit_percentage = ((1 - total_price) / total_price) * 100
                    
                    # Calculate optimal positions
                    strategy = {
                        "action": "buy_all_outcomes",
                        "positions": {
                            outcome: price 
                            for outcome, price in market.prices.items()
                        },
                        "total_cost": total_price,
                        "guaranteed_return": 1.0,
                        "net_profit": 1.0 - total_price
                    }
                    
                    opportunity = ArbitrageOpportunity(
                        opportunity_type=OpportunityType.INTRA_PLATFORM,
                        market_ids=[market.id],
                        platforms=[platform.platform_name],
                        description=(
                            f"Buy all outcomes in '{market.question}' "
                            f"for total cost {total_price:.4f}"
                        ),
                        profit_percentage=profit_percentage,
                        strategy=strategy,
                        confidence=0.95 if total_price < 0.95 else 0.85
                    )
                    
                    opportunities.append(opportunity)
        
        except Exception as e:
            print(f"Error finding intra-platform opportunities on {platform.platform_name}: {e}")
        
        return opportunities
    
    def find_cross_platform_opportunities(self) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities across multiple platforms.
        
        This looks for the same market on different platforms with price discrepancies.
        
        Returns:
            List of cross-platform arbitrage opportunities
        """
        opportunities = []
        
        try:
            # Collect markets from all platforms
            platform_markets: Dict[str, List[Market]] = {}
            for platform in self.platforms:
                platform_markets[platform.platform_name] = platform.get_markets(limit=100)
            
            # Find matching markets across platforms
            matched_markets = self._match_markets_across_platforms(platform_markets)
            
            # Analyze each matched market group for arbitrage
            for market_group in matched_markets:
                cross_opps = self._analyze_cross_platform_market_group(market_group)
                opportunities.extend(cross_opps)
        
        except Exception as e:
            print(f"Error finding cross-platform opportunities: {e}")
        
        return opportunities
    
    def _match_markets_across_platforms(
        self, 
        platform_markets: Dict[str, List[Market]]
    ) -> List[List[Market]]:
        """
        Match markets across platforms based on similar questions.
        
        Args:
            platform_markets: Dictionary mapping platform names to their markets
            
        Returns:
            List of market groups (each group contains matching markets)
        """
        matched_groups = []
        
        # Simple matching based on question similarity
        # In production, this would use more sophisticated matching
        platform_names = list(platform_markets.keys())
        
        for i, platform1 in enumerate(platform_names):
            for platform2 in platform_names[i+1:]:
                markets1 = platform_markets[platform1]
                markets2 = platform_markets[platform2]
                
                for market1 in markets1:
                    for market2 in markets2:
                        # Simple similarity check (can be improved)
                        if self._markets_similar(market1, market2):
                            matched_groups.append([market1, market2])
        
        return matched_groups
    
    def _markets_similar(self, market1: Market, market2: Market) -> bool:
        """
        Check if two markets are similar enough to be the same event.
        
        Args:
            market1: First market
            market2: Second market
            
        Returns:
            True if markets are likely the same
        """
        # Simple implementation - check if questions are very similar
        q1 = market1.question.lower().strip()
        q2 = market2.question.lower().strip()
        
        # Direct match
        if q1 == q2:
            return True
        
        # Substring match (longer than 20 chars)
        if len(q1) > 20 and len(q2) > 20:
            if q1 in q2 or q2 in q1:
                return True
        
        return False
    
    def _analyze_cross_platform_market_group(
        self, 
        markets: List[Market]
    ) -> List[ArbitrageOpportunity]:
        """
        Analyze a group of matched markets for cross-platform arbitrage.
        
        Args:
            markets: List of matching markets from different platforms
            
        Returns:
            List of arbitrage opportunities found
        """
        opportunities = []
        
        if len(markets) < 2:
            return opportunities
        
        # Check for price discrepancies in common outcomes
        # Find common outcomes
        common_outcomes = self._find_common_outcomes(markets)
        
        for outcome in common_outcomes:
            prices = []
            for market in markets:
                price = market.get_price(outcome)
                if price is not None:
                    prices.append((market, price))
            
            if len(prices) >= 2:
                # Sort by price
                prices.sort(key=lambda x: x[1])
                lowest_price_market, lowest_price = prices[0]
                highest_price_market, highest_price = prices[-1]
                
                # Calculate potential profit
                price_diff = highest_price - lowest_price
                if price_diff > 0.01:  # Minimum 1 cent difference
                    profit_percentage = (price_diff / lowest_price) * 100
                    
                    strategy = {
                        "action": "buy_low_sell_high",
                        "buy_platform": lowest_price_market.platform,
                        "buy_price": lowest_price,
                        "sell_platform": highest_price_market.platform,
                        "sell_price": highest_price,
                        "outcome": outcome,
                        "price_difference": price_diff
                    }
                    
                    opportunity = ArbitrageOpportunity(
                        opportunity_type=OpportunityType.CROSS_PLATFORM,
                        market_ids=[m.id for m in markets],
                        platforms=[m.platform for m in markets],
                        description=(
                            f"Buy '{outcome}' at {lowest_price:.4f} on "
                            f"{lowest_price_market.platform}, sell at {highest_price:.4f} "
                            f"on {highest_price_market.platform}"
                        ),
                        profit_percentage=profit_percentage,
                        strategy=strategy,
                        confidence=0.80  # Lower confidence due to execution risk
                    )
                    
                    opportunities.append(opportunity)
        
        return opportunities
    
    def _find_common_outcomes(self, markets: List[Market]) -> Set[str]:
        """
        Find outcomes that exist in all markets.
        
        Args:
            markets: List of markets
            
        Returns:
            Set of common outcome names
        """
        if not markets:
            return set()
        
        common = set(markets[0].outcomes)
        for market in markets[1:]:
            common &= set(market.outcomes)
        
        return common
