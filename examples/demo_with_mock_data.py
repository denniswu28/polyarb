"""
Demo script showing polyarb functionality with mock data.

This demonstrates the arbitrage detection without requiring API access.
"""

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
    
    # Polymarket demo markets
    polymarket_markets = [
        Market(
            id="poly_1",
            platform="Polymarket",
            question="Will the next SpaceX launch be successful?",
            outcomes=["Yes", "No"],
            prices={"Yes": 0.43, "No": 0.52},  # Total: 0.95 - Arbitrage opportunity!
            volume=50000.0
        ),
        Market(
            id="poly_2",
            platform="Polymarket",
            question="Will it snow in NYC this weekend?",
            outcomes=["Yes", "No"],
            prices={"Yes": 0.30, "No": 0.70},  # Total: 1.00 - No arbitrage
            volume=10000.0
        ),
        Market(
            id="poly_3",
            platform="Polymarket",
            question="Will candidate X win the election?",
            outcomes=["Yes", "No"],
            prices={"Yes": 0.60, "No": 0.38},  # Total: 0.98 - Small arbitrage
            volume=100000.0
        ),
    ]
    
    # PredictIt demo markets (showing cross-platform opportunity)
    predictit_markets = [
        Market(
            id="pred_1",
            platform="PredictIt",
            question="Will candidate X win the election?",  # Same as poly_3
            outcomes=["Yes", "No"],
            prices={"Yes": 0.72, "No": 0.30},  # Yes is more expensive - arbitrage!
            volume=80000.0
        ),
    ]
    
    return polymarket_markets, predictit_markets


def main():
    """Run the demo."""
    print("=" * 70)
    print("Polyarb Demo - Arbitrage Detection with Mock Data")
    print("=" * 70)
    print()
    
    # Create demo platforms
    polymarket_markets, predictit_markets = create_demo_data()
    polymarket = DemoPlatform("Polymarket (Demo)", polymarket_markets)
    predictit = DemoPlatform("PredictIt (Demo)", predictit_markets)
    
    print("Demo Platforms Initialized:")
    print(f"  • {polymarket.platform_name}: {len(polymarket_markets)} markets")
    print(f"  • {predictit.platform_name}: {len(predictit_markets)} markets")
    print()
    
    # Create arbitrage engine
    engine = ArbitrageEngine(
        platforms=[polymarket, predictit],
        min_profit_threshold=0.5,  # 0.5% minimum profit
        max_total_price_threshold=0.99  # Allow up to 0.99 total for intra-platform
    )
    
    print("Analyzing markets for arbitrage opportunities...")
    print("-" * 70)
    print()
    
    # Find opportunities
    opportunities = engine.find_opportunities()
    
    if not opportunities:
        print("No arbitrage opportunities found.")
        return
    
    print(f"Found {len(opportunities)} arbitrage opportunity(ies):\n")
    
    # Display opportunities
    for i, opp in enumerate(opportunities, 1):
        print(f"{'#' * 70}")
        print(f"Opportunity #{i}: {opp.opportunity_type.value.upper()}")
        print(f"{'#' * 70}")
        print()
        print(f"Platform(s):      {', '.join(opp.platforms)}")
        print(f"Expected Profit:  {opp.profit_percentage:.2f}%")
        print(f"Confidence:       {opp.confidence:.0%}")
        print(f"Description:      {opp.description}")
        print()
        print(f"Strategy:         {opp.strategy.get('action', 'N/A')}")
        
        if opp.opportunity_type == OpportunityType.INTRA_PLATFORM:
            print()
            print("Positions to take:")
            for outcome, price in opp.strategy.get("positions", {}).items():
                print(f"  • Buy {outcome}: ${price:.4f}")
            
            print()
            print(f"Total Investment:    ${opp.strategy.get('total_cost', 0):.4f}")
            print(f"Guaranteed Return:   ${opp.strategy.get('guaranteed_return', 0):.4f}")
            print(f"Net Profit:          ${opp.strategy.get('net_profit', 0):.4f}")
            print(f"ROI:                 {opp.profit_percentage:.2f}%")
        
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
            print(f"Profit per share:     {opp.profit_percentage:.2f}%")
        
        print()
    
    print("=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print()
    print("Key Insights:")
    print("  • Intra-platform arbitrage: Buy all outcomes when sum < 1")
    print("  • Cross-platform arbitrage: Buy low on one platform, sell high on another")
    print("  • Always consider transaction fees and execution risk in real trading")


if __name__ == "__main__":
    main()
