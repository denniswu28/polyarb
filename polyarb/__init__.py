"""Prediction-market research scanning with deterministic simulated execution.

Polymarket data/scanning paths are the only platform-specific paths reported as
owner-validated. PredictIt, Kalshi, and live order submission fail closed.
"""

__version__ = "0.1.0"

from polyarb.core.arbitrage_engine import ArbitrageEngine
from polyarb.core.opportunity import ArbitrageOpportunity
from polyarb.platforms.base import PlatformInterface

__all__ = ["ArbitrageEngine", "ArbitrageOpportunity", "PlatformInterface"]
