"""Fail-closed Kalshi placeholder; no integration behavior is implemented."""

from typing import List, Optional

from polyarb.platforms.base import PlatformInterface, Market


class KalshiPlatform(PlatformInterface):
    """Fail-closed placeholder; Kalshi behavior is not implemented or validated."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize Kalshi platform interface.
        
        Args:
            api_key: API key for Kalshi
            **kwargs: Additional configuration
        """
        super().__init__(api_key, **kwargs)
        # No client is initialized; methods below fail closed.
    
    @property
    def platform_name(self) -> str:
        """Return the platform name."""
        return "Kalshi"
    
    def get_markets(self, limit: Optional[int] = None) -> List[Market]:
        """
        Fetch available markets from Kalshi.
        
        Args:
            limit: Optional limit on number of markets to fetch
            
        Returns:
            List of Market objects
        """
        raise NotImplementedError(
            "Kalshi integration is not implemented or validated."
        )
    
    def get_market(self, market_id: str) -> Optional[Market]:
        """
        Fetch a specific market by ID from Kalshi.
        
        Args:
            market_id: The unique identifier for the market
            
        Returns:
            Market object if found, None otherwise
        """
        raise NotImplementedError(
            "Kalshi integration is not implemented or validated."
        )

    def initialize(self) -> bool:
        """Fail closed instead of reporting a successful connection."""
        raise NotImplementedError(
            "Kalshi integration is not implemented or validated."
        )
