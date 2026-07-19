"""Deterministic offline scanner example using synthetic market snapshots only."""

from polyarb import ArbitrageEngine
from polyarb.platforms.base import Market
from polyarb.core.opportunity import OpportunityType


class DemoPlatform:
    """Demo platform with hardcoded markets for demonstration."""
    
    def __init__(self, name, markets):
        self.name = name
        self._markets = markets
    
    @property
    def platform_name(self):
        return self.name
    
    def get_markets(self, limit=None):
        if limit:
            return self._markets[:limit]
        return self._markets
    
    def get_market(self, market_id):
        for market in self._markets:
            if market.id == market_id:
                return market
        return None


def create_demo_data():
    """Create demo markets for demonstration."""
    
    venue_a_markets = [
        Market(
            id="poly_1",
            platform="SyntheticVenueA",
            question="Will the next SpaceX launch be successful?",
            outcomes=["Yes", "No"],
            prices={"Yes": 0.43, "No": 0.52},
            volume=50000.0
        ),
        Market(
            id="poly_2",
            platform="SyntheticVenueA",
            question="Will it snow in NYC this weekend?",
            outcomes=["Yes", "No"],
            prices={"Yes": 0.30, "No": 0.70},
            volume=10000.0
        ),
        Market(
            id="poly_3",
            platform="SyntheticVenueA",
            question="Will candidate X win the election?",
            outcomes=["Yes", "No"],
            prices={"Yes": 0.60, "No": 0.38},
            volume=100000.0
        ),
    ]
    
    venue_b_markets = [
        Market(
            id="pred_1",
            platform="SyntheticVenueB",
            question="Will candidate X win the election?",
            outcomes=["Yes", "No"],
            prices={"Yes": 0.72, "No": 0.30},
            volume=80000.0
        ),
    ]
    
    return venue_a_markets, venue_b_markets


def main():
    """Run the demo."""
    print("=" * 70)
    print("Polyarb - deterministic synthetic opportunity scan")
    print("=" * 70)
    print()
    
    # Create demo platforms
    venue_a_markets, venue_b_markets = create_demo_data()
    venue_a = DemoPlatform("SyntheticVenueA", venue_a_markets)
    venue_b = DemoPlatform("SyntheticVenueB", venue_b_markets)
    
    print("Demo Platforms Initialized:")
    print(f"  - {venue_a.platform_name}: {len(venue_a_markets)} markets")
    print(f"  - {venue_b.platform_name}: {len(venue_b_markets)} markets")
    print()
    
    # Create arbitrage engine
    engine = ArbitrageEngine(
        platforms=[venue_a, venue_b],
        min_profit_threshold=0.5,
        max_total_price_threshold=0.99,
        fee_rate_bps=10.0,
        slippage_bps=10.0,
    )
    
    print("Scanning synthetic quotes under explicit 10 bps fee + 10 bps slippage assumptions...")
    print("-" * 70)
    print()
    
    # Find opportunities
    opportunities = engine.find_opportunities()
    
    if not opportunities:
        print("No model-implied candidates found.")
        return
    
    print(f"Found {len(opportunities)} model-implied candidate(s):\n")
    
    # Display opportunities
    for i, opp in enumerate(opportunities, 1):
        print(f"{'#' * 70}")
        print(f"Opportunity #{i}: {opp.opportunity_type.value.upper()}")
        print(f"{'#' * 70}")
        print()
        print(f"Platform(s):      {', '.join(opp.platforms)}")
        print(f"Modeled edge:     {opp.profit_percentage:.2f}%")
        print(f"Description:      {opp.description}")
        print()
        print(f"Strategy:         {opp.strategy.get('action', 'N/A')}")
        
        if opp.opportunity_type == OpportunityType.INTRA_PLATFORM:
            print()
            print("Modeled basket:")
            for outcome, price in opp.strategy.get("positions", {}).items():
                print(f"  - Buy {outcome}: ${price:.4f}")
            
            print()
            print(f"Quoted basket cost:  ${opp.strategy.get('total_cost', 0):.4f}")
            print(
                "Cost after assumptions: "
                f"${opp.strategy.get('modeled_cost_after_fees_and_slippage', 0):.4f}"
            )
            print(f"Model-implied edge:  ${opp.strategy.get('model_implied_edge', 0):.4f}")
        
        elif opp.opportunity_type == OpportunityType.CROSS_PLATFORM:
            print()
            buy_platform = opp.strategy.get('buy_platform', 'N/A')
            buy_price = opp.strategy.get('buy_price', 0)
            sell_platform = opp.strategy.get('sell_platform', 'N/A')
            sell_price = opp.strategy.get('sell_price', 0)
            outcome = opp.strategy.get('outcome', 'N/A')
            
            print(f"Outcome:              {outcome}")
            print(f"Buy on:               {buy_platform} at ${buy_price:.4f}")
            print(f"Sell on:              {sell_platform} at ${sell_price:.4f}")
            print(f"Price Difference:     ${opp.strategy.get('price_difference', 0):.4f}")
            print(f"Model-implied edge:   {opp.profit_percentage:.2f}%")
        
        print()
    
    print("=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print()
    print("Boundaries:")
    print("  - Inputs are deterministic synthetic quotes, not market or account data.")
    print("  - Results are detected candidates, not approved, submitted, filled, or settled trades.")
    print("  - Contract equivalence, rules, liquidity, fees, and execution require independent review.")


if __name__ == "__main__":
    main()
