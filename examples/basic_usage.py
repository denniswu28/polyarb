"""
Example usage of the polyarb arbitrage engine.

This script demonstrates how to use the arbitrage engine to find opportunities
on Polymarket and potentially other platforms.
"""

from polyarb import ArbitrageEngine
from polyarb.platforms.polymarket import PolymarketPlatform
from polyarb.config import Config


def main():
    """Main example function."""
    print("=" * 60)
    print("Polyarb - Arbitrage Detection Engine")
    print("=" * 60)
    print()
    
    # Load configuration
    config = Config()
    
    # Initialize platforms
    print("Initializing platforms...")
    polymarket = PolymarketPlatform(
        api_key=config.get("polymarket_api_key")
    )
    print(f"✓ {polymarket.platform_name} initialized")
    print()
    
    # Create arbitrage engine
    engine = ArbitrageEngine(
        platforms=[polymarket],
        min_profit_threshold=config.get("min_profit_threshold", 1.0),
        max_total_price_threshold=config.get("max_total_price_threshold", 0.98)
    )
    
    print("Searching for arbitrage opportunities...")
    print("-" * 60)
    print()
    
    # Find opportunities
    opportunities = engine.find_opportunities()
    
    if not opportunities:
        print("No arbitrage opportunities found at this time.")
        print()
        print("This could mean:")
        print("  • Markets are efficiently priced")
        print("  • No markets meet the profit threshold")
        print("  • API returned no data (check connection)")
        return
    
    # Display opportunities
    print(f"Found {len(opportunities)} arbitrage opportunity(ies):\n")
    
    for i, opp in enumerate(opportunities, 1):
        print(f"Opportunity #{i}")
        print(f"  Type: {opp.opportunity_type.value}")
        print(f"  Platform(s): {', '.join(opp.platforms)}")
        print(f"  Expected Profit: {opp.profit_percentage:.2f}%")
        print(f"  Confidence: {opp.confidence:.0%}")
        print(f"  Description: {opp.description}")
        print(f"  Strategy: {opp.strategy.get('action', 'N/A')}")
        
        if opp.strategy.get("positions"):
            print(f"  Positions:")
            for outcome, price in opp.strategy["positions"].items():
                print(f"    • {outcome}: ${price:.4f}")
        
        if opp.strategy.get("total_cost"):
            print(f"  Total Cost: ${opp.strategy['total_cost']:.4f}")
            print(f"  Guaranteed Return: ${opp.strategy.get('guaranteed_return', 0):.4f}")
            print(f"  Net Profit: ${opp.strategy.get('net_profit', 0):.4f}")
        
        print()
    
    print("=" * 60)
    print("Analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
