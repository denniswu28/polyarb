"""Research engine for model-implied prediction-market candidates."""

import math
from typing import List, Dict, Optional, Set

from polyarb.platforms.base import PlatformInterface, Market
from polyarb.core.opportunity import ArbitrageOpportunity, OpportunityType


class ArbitrageEngine:
    """
    Engine for detecting basket and quote-discrepancy research candidates.
    """
    
    def __init__(
        self,
        platforms: Optional[List[PlatformInterface]] = None,
        min_profit_threshold: float = 1.0,
        max_total_price_threshold: float = 0.98,
        fee_rate_bps: float = 0.0,
        slippage_bps: float = 0.0,
    ):
        """
        Initialize the arbitrage engine.
        
        Args:
            platforms: List of platform interfaces to monitor
            min_profit_threshold: Minimum model-edge percentage to report (default 1%)
            max_total_price_threshold: Maximum conditional basket cost (default 0.98)
            fee_rate_bps: Explicit fee assumption applied to modeled transaction value
            slippage_bps: Explicit slippage assumption applied to modeled transaction value
        """
        self.platforms = platforms or []
        self.min_profit_threshold = self._finite_float(
            min_profit_threshold,
            "min_profit_threshold",
        )
        self.max_total_price_threshold = self._finite_float(
            max_total_price_threshold,
            "max_total_price_threshold",
        )
        self.fee_rate_bps = self._finite_float(fee_rate_bps, "fee_rate_bps")
        self.slippage_bps = self._finite_float(slippage_bps, "slippage_bps")
        self._validate_config()

    @staticmethod
    def _finite_float(value: object, name: str) -> float:
        try:
            normalized = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be finite") from exc
        if not math.isfinite(normalized):
            raise ValueError(f"{name} must be finite")
        return normalized

    def _validate_config(self) -> None:
        """Reject non-finite limits, including configuration mutated after init."""
        self.min_profit_threshold = self._finite_float(
            self.min_profit_threshold,
            "min_profit_threshold",
        )
        self.max_total_price_threshold = self._finite_float(
            self.max_total_price_threshold,
            "max_total_price_threshold",
        )
        self.fee_rate_bps = self._finite_float(self.fee_rate_bps, "fee_rate_bps")
        self.slippage_bps = self._finite_float(self.slippage_bps, "slippage_bps")
        if self.fee_rate_bps < 0 or self.slippage_bps < 0:
            raise ValueError("fee_rate_bps and slippage_bps must be non-negative")

    def _cost_adjustment(self, transaction_value: float) -> float:
        """Return configured fees and slippage for a modeled transaction value."""
        self._validate_config()
        transaction_value = self._finite_float(
            transaction_value,
            "transaction_value",
        )
        return self._finite_float(
            transaction_value * (self.fee_rate_bps + self.slippage_bps) / 10000,
            "cost adjustment",
        )
    
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
        Find all research candidates across registered platforms.
        
        Returns:
            List of ArbitrageOpportunity objects
        """
        self._validate_config()
        opportunities = []
        
        # Find intra-platform opportunities for each platform
        for platform in self.platforms:
            intra_opps = self.find_intra_platform_opportunities(platform)
            opportunities.extend(intra_opps)
        
        # Find cross-platform opportunities
        if len(self.platforms) > 1:
            cross_opps = self.find_cross_platform_opportunities()
            opportunities.extend(cross_opps)
        
        # Filter by the backward-compatible model-edge threshold.
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
        Find conditional basket candidates within a single platform.
        
        This looks for markets where the sum of executable outcome asks is less
        than 1, under a conditional payoff assumption that must be reviewed
        separately. Reference, midpoint, and last-trade prices fail closed.
        
        Args:
            platform: Platform to analyze
            
        Returns:
            List of intra-platform research candidates
        """
        opportunities = []

        markets = platform.get_markets(limit=100)

        for market in markets:
            ask_prices = {
                outcome: market.get_executable_price(outcome, "buy")
                for outcome in market.outcomes
            }
            if len(ask_prices) < 2 or any(price is None for price in ask_prices.values()):
                continue

            try:
                ask_prices = {
                    outcome: self._finite_float(price, f"{outcome} ask price")
                    for outcome, price in ask_prices.items()
                }
            except ValueError:
                continue

            # Calculate total price from executable asks only.
            total_price = self._finite_float(sum(ask_prices.values()), "total price")

            # Skip malformed markets to avoid division errors
            if total_price <= 0:
                continue

            effective_total_price = self._finite_float(
                total_price + self._cost_adjustment(total_price),
                "effective total price",
            )

            # The model reports a candidate only after explicit cost assumptions.
            if effective_total_price < self.max_total_price_threshold:
                profit_percentage = self._finite_float(
                    (1 - effective_total_price) / effective_total_price * 100,
                    "model edge percentage",
                )

                # Calculate optimal positions
                strategy = {
                    "action": "buy_all_outcomes",
                    "positions": dict(ask_prices),
                    "price_semantics": "executable_asks",
                    "total_cost": total_price,
                    "modeled_cost_after_fees_and_slippage": effective_total_price,
                    "fee_rate_bps": self.fee_rate_bps,
                    "slippage_bps": self.slippage_bps,
                    "modeled_payoff": 1.0,
                    "payoff_assumption_is_conditional": True,
                    "model_implied_edge": 1.0 - effective_total_price,
                }

                opportunity = ArbitrageOpportunity(
                    opportunity_type=OpportunityType.INTRA_PLATFORM,
                    market_ids=[market.id],
                    platforms=[platform.platform_name],
                    description=(
                        f"Buy all outcomes in '{market.question}' "
                        f"for quoted cost {total_price:.4f}; model-implied payoff "
                        "coverage requires contract and resolution review"
                    ),
                    profit_percentage=profit_percentage,
                    strategy=strategy,
                    confidence=0.0,
                )

                opportunities.append(opportunity)

        return opportunities
    
    def find_cross_platform_opportunities(self) -> List[ArbitrageOpportunity]:
        """
        Find cross-platform quote-discrepancy candidates.
        
        This looks for the same market on different platforms with price discrepancies.
        
        Returns:
            List of cross-platform research candidates
        """
        opportunities = []

        # Collect markets from all platforms
        platform_markets: Dict[str, List[Market]] = {}
        for platform in self.platforms:
            platform_markets[platform.platform_name] = platform.get_markets(limit=100)

        # Find matching markets across platforms
        matched_markets = self._match_markets_across_platforms(platform_markets)

        # Analyze each asserted matching group for quote discrepancies.
        for market_group in matched_markets:
            cross_opps = self._analyze_cross_platform_market_group(market_group)
            opportunities.extend(cross_opps)

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
        # This heuristic does not establish contract equivalence.
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
        Analyze a group of asserted matches for quote discrepancies.
        
        Args:
            markets: List of matching markets from different platforms
            
        Returns:
            List of research candidates found
        """
        opportunities = []
        
        if len(markets) < 2:
            return opportunities
        
        # Compare executable asks for buys with executable bids for sells.
        common_outcomes = self._find_common_outcomes(markets)
        
        for outcome in sorted(common_outcomes):
            executable_pairs = []
            for buy_market in markets:
                ask = buy_market.get_executable_price(outcome, "buy")
                if ask is None:
                    continue
                try:
                    ask = self._finite_float(ask, f"{outcome} ask price")
                except ValueError:
                    continue
                for sell_market in markets:
                    if sell_market is buy_market or sell_market.platform == buy_market.platform:
                        continue
                    bid = sell_market.get_executable_price(outcome, "sell")
                    if bid is not None:
                        try:
                            bid = self._finite_float(bid, f"{outcome} bid price")
                        except ValueError:
                            continue
                        executable_pairs.append((buy_market, ask, sell_market, bid))

            if executable_pairs:
                # Stable tie-breaking keeps the offline example reproducible.
                executable_pairs.sort(
                    key=lambda item: (
                        -(item[3] - item[1]),
                        item[0].platform,
                        item[0].id,
                        item[2].platform,
                        item[2].id,
                    )
                )
                (
                    lowest_price_market,
                    lowest_price,
                    highest_price_market,
                    highest_price,
                ) = executable_pairs[0]
                
                # Calculate the modeled quote discrepancy after explicit costs.
                price_diff = self._finite_float(
                    highest_price - lowest_price,
                    "price difference",
                )
                if lowest_price <= 0:
                    continue

                modeled_costs = self._cost_adjustment(lowest_price + highest_price)
                modeled_edge = self._finite_float(
                    price_diff - modeled_costs,
                    "modeled edge",
                )
                if modeled_edge > 0.01:  # Minimum modeled 1 cent discrepancy
                    profit_percentage = self._finite_float(
                        modeled_edge / lowest_price * 100,
                        "model edge percentage",
                    )
                    
                    strategy = {
                        "action": "buy_low_sell_high",
                        "buy_platform": lowest_price_market.platform,
                        "buy_price": lowest_price,
                        "sell_platform": highest_price_market.platform,
                        "sell_price": highest_price,
                        "buy_price_semantics": "executable_ask",
                        "sell_price_semantics": "executable_bid",
                        "outcome": outcome,
                        "price_difference": price_diff,
                        "model_implied_edge": modeled_edge,
                        "fee_rate_bps": self.fee_rate_bps,
                        "slippage_bps": self.slippage_bps,
                    }
                    
                    opportunity = ArbitrageOpportunity(
                        opportunity_type=OpportunityType.CROSS_PLATFORM,
                        market_ids=[m.id for m in markets],
                        platforms=[m.platform for m in markets],
                        description=(
                            f"Buy '{outcome}' at {lowest_price:.4f} on "
                            f"{lowest_price_market.platform}, sell at {highest_price:.4f} "
                            f"on {highest_price_market.platform}; candidate requires "
                            "contract-equivalence, rules, and executable-hedge review"
                        ),
                        profit_percentage=profit_percentage,
                        strategy=strategy,
                        confidence=0.0,
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
