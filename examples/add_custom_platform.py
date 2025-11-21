"""
Example: How to add a new platform integration.

This example shows how to extend polyarb with a new prediction market platform.
"""

from typing import List, Optional
from polyarb.platforms.base import PlatformInterface, Market
from polyarb import ArbitrageEngine


# Step 1: Create a new platform class that extends PlatformInterface
class CustomPlatform(PlatformInterface):
    """Example custom platform integration."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize the custom platform.
        
        Args:
            api_key: Optional API key for authentication
            **kwargs: Additional configuration options
        """
        super().__init__(api_key, **kwargs)
        self.base_url = kwargs.get('base_url', 'https://api.customplatform.com')
        # Initialize your API client here
    
    @property
    def platform_name(self) -> str:
        """Return the name of your platform."""
        return "CustomPlatform"
    
    def get_markets(self, limit: Optional[int] = None) -> List[Market]:
        """
        Fetch markets from your platform's API.
        
        Args:
            limit: Optional limit on number of markets
            
        Returns:
            List of Market objects
        """
        # Step 2: Implement API call to fetch markets
        # Example implementation:
        try:
            # response = requests.get(f"{self.base_url}/markets", params={"limit": limit})
            # data = response.json()
            
            # For this example, return mock data
            markets = [
                Market(
                    id="custom_1",
                    platform=self.platform_name,
                    question="Example question?",
                    outcomes=["Yes", "No"],
                    prices={"Yes": 0.55, "No": 0.45}
                )
            ]
            return markets
        
        except Exception as e:
            print(f"Error fetching markets: {e}")
            return []
    
    def get_market(self, market_id: str) -> Optional[Market]:
        """
        Fetch a specific market by ID.
        
        Args:
            market_id: The market identifier
            
        Returns:
            Market object or None
        """
        # Step 3: Implement single market fetch
        # Example implementation:
        try:
            # response = requests.get(f"{self.base_url}/markets/{market_id}")
            # data = response.json()
            
            # For this example, return mock data
            markets = self.get_markets()
            for market in markets:
                if market.id == market_id:
                    return market
            return None
        
        except Exception as e:
            print(f"Error fetching market {market_id}: {e}")
            return None


def main():
    """Demo of using the custom platform."""
    
    print("=" * 70)
    print("Example: Adding a Custom Platform to Polyarb")
    print("=" * 70)
    print()
    
    # Step 4: Initialize your custom platform
    custom_platform = CustomPlatform(
        api_key="your_api_key_here",
        base_url="https://api.customplatform.com"
    )
    
    print(f"✓ Initialized {custom_platform.platform_name}")
    print()
    
    # Step 5: Add it to the arbitrage engine
    engine = ArbitrageEngine(
        platforms=[custom_platform],
        min_profit_threshold=1.0
    )
    
    print(f"✓ Added {custom_platform.platform_name} to arbitrage engine")
    print()
    
    # Step 6: Use it like any other platform
    print("Fetching markets...")
    markets = custom_platform.get_markets()
    print(f"  Found {len(markets)} market(s)")
    print()
    
    for market in markets:
        print(f"  • {market.question}")
        for outcome, price in market.prices.items():
            print(f"    {outcome}: ${price:.2f}")
    print()
    
    # Step 7: Find arbitrage opportunities
    print("Searching for arbitrage opportunities...")
    opportunities = engine.find_opportunities()
    
    if opportunities:
        print(f"  Found {len(opportunities)} opportunity(ies)!")
    else:
        print("  No opportunities found at this time.")
    
    print()
    print("=" * 70)
    print("That's it! Your custom platform is now integrated.")
    print("=" * 70)
    print()
    print("Key Points:")
    print("  1. Extend PlatformInterface")
    print("  2. Implement platform_name, get_markets(), and get_market()")
    print("  3. Parse your API responses into Market objects")
    print("  4. Add to ArbitrageEngine like any other platform")
    print()
    print("The arbitrage engine will automatically:")
    print("  • Detect intra-platform opportunities on your platform")
    print("  • Detect cross-platform opportunities with other platforms")
    print("  • Apply your configured profit thresholds")


if __name__ == "__main__":
    main()
