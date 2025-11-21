"""
Polyarb - Arbitrage machine for prediction markets.

This package provides tools for detecting and executing arbitrage opportunities
across prediction market platforms including Polymarket, PredictIt, and Kalshi.
"""

__version__ = "0.1.0"

from polyarb.core.arbitrage_engine import ArbitrageEngine
from polyarb.core.opportunity import ArbitrageOpportunity
from polyarb.platforms.base import PlatformInterface

__all__ = ["ArbitrageEngine", "ArbitrageOpportunity", "PlatformInterface"]
