"""
Configuration management for polyarb.
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv


class Config:
    """Configuration management for the arbitrage engine."""
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            env_file: Optional path to .env file
        """
        if env_file and os.path.exists(env_file):
            load_dotenv(env_file)
        else:
            load_dotenv()  # Load from default .env if exists
        
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        return {
            # Platform API keys
            "polymarket_api_key": os.getenv("POLYMARKET_API_KEY"),
            "predictit_api_key": os.getenv("PREDICTIT_API_KEY"),
            "kalshi_api_key": os.getenv("KALSHI_API_KEY"),
            
            # Engine settings
            "min_profit_threshold": float(os.getenv("MIN_PROFIT_THRESHOLD", "1.0")),
            "max_total_price_threshold": float(os.getenv("MAX_TOTAL_PRICE_THRESHOLD", "0.98")),
            "refresh_interval": int(os.getenv("REFRESH_INTERVAL", "60")),
            
            # Feature flags
            "enable_cross_platform": os.getenv("ENABLE_CROSS_PLATFORM", "true").lower() == "true",
            "enable_intra_platform": os.getenv("ENABLE_INTRA_PLATFORM", "true").lower() == "true",
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self._config.get(key, default)
    
    def __getitem__(self, key: str) -> Any:
        """Get configuration value using dictionary syntax."""
        return self._config[key]
    
    def __contains__(self, key: str) -> bool:
        """Check if configuration key exists."""
        return key in self._config
