"""
Example usage of the polyarb arbitrage engine.

This opt-in example contacts Polymarket public endpoints. It detects research
candidates only and cannot submit orders.
"""

from polyarb import ArbitrageEngine
from polyarb.platforms.polymarket import PolymarketPlatform
from polyarb.config import Config


def main():
    """Main example function."""
    print("=" * 60)
    print("Polyarb - opt-in Polymarket public-data scan")
    print("=" * 60)
    print()
    
    # Load configuration
    config = Config()
    
    # Initialize platforms
    print("Preparing public-data client...")
    polymarket = PolymarketPlatform(
        api_key=config.get("polymarket_api_key")
    )
    print(f"- {polymarket.platform_name} client prepared")
    print()
    
    # Create arbitrage engine
    engine = ArbitrageEngine(
        platforms=[polymarket],
        min_profit_threshold=config.get("min_profit_threshold", 1.0),
        max_total_price_threshold=config.get("max_total_price_threshold", 0.98),
        fee_rate_bps=config.get("fee_rate_bps", 0.0),
        slippage_bps=config.get("slippage_bps", 0.0),
    )
    
    print("Searching for model-implied research candidates...")
    print("-" * 60)
    print()
    
    # Find opportunities
    try:
        opportunities = engine.find_opportunities()
    except Exception as exc:
        print("Arbitrage scan failed due to an unexpected error.")
        print(f"  - Details: {exc}")
        raise
    
    if not opportunities:
        print("No candidates met the configured assumptions and threshold.")
        print()
        print("This could mean:")
        print("  - No quotes meet the configured model threshold")
        print("  - API returned no usable data")
        return
    
    # Display opportunities
    print(f"Found {len(opportunities)} arbitrage opportunity(ies):\n")
    
    for i, opp in enumerate(opportunities, 1):
        print(f"Opportunity #{i}")
        print(f"  Type: {opp.opportunity_type.value}")
        print(f"  Platform(s): {', '.join(opp.platforms)}")
        print(f"  Model-implied edge: {opp.profit_percentage:.2f}%")
        print(f"  Description: {opp.description}")
        print(f"  Strategy: {opp.strategy.get('action', 'N/A')}")
        
        if opp.strategy.get("positions"):
            print("  Modeled basket:")
            for outcome, price in opp.strategy["positions"].items():
                print(f"    - {outcome}: ${price:.4f}")
        
        if opp.strategy.get("total_cost"):
            print(f"  Total Cost: ${opp.strategy['total_cost']:.4f}")
            print(
                "  Cost after assumptions: "
                f"${opp.strategy.get('modeled_cost_after_fees_and_slippage', 0):.4f}"
            )
            print(f"  Model-implied edge: ${opp.strategy.get('model_implied_edge', 0):.4f}")
        
        print()
    
    print("=" * 60)
    print("Analysis complete!")
    print("Candidates are not approved, submitted, filled, settled, or reported trades.")
    print("=" * 60)


if __name__ == "__main__":
    main()
