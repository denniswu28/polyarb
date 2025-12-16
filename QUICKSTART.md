# Quick Start Guide

## Installation

```bash
pip install -r requirements.txt
```

## Basic Usage

### 1. Run the Demo (Recommended First Step)
```bash
cd /home/runner/work/polyarb/polyarb
PYTHONPATH=/home/runner/work/polyarb/polyarb:$PYTHONPATH python examples/demo_with_mock_data.py
```

This will show you 4 example arbitrage opportunities using mock data.

### 2. Try Real Polymarket Data
```bash
PYTHONPATH=/home/runner/work/polyarb/polyarb:$PYTHONPATH python examples/basic_usage.py
```

Note: Requires internet connection to Polymarket API.

### 3. Explore the Enhanced System
```bash
PYTHONPATH=/home/runner/work/polyarb/polyarb:$PYTHONPATH python examples/enhanced_system_demo.py
```

This runs the comprehensive demo that wires together the enhanced architecture modules (data, strategy templates, embeddings, scanners, execution, and reporting). See `ENHANCED_SYSTEM.md` for a module-by-module overview.

### 4. Run Tests
```bash
PYTHONPATH=/home/runner/work/polyarb/polyarb:$PYTHONPATH python -m pytest tests/ -v
```

## Simple Python Script

```python
from polyarb import ArbitrageEngine
from polyarb.platforms.polymarket import PolymarketPlatform

# Initialize
polymarket = PolymarketPlatform()
engine = ArbitrageEngine(platforms=[polymarket], min_profit_threshold=1.0)

# Find opportunities
opportunities = engine.find_opportunities()

# Display
for opp in opportunities:
    print(f"Profit: {opp.profit_percentage:.2f}%")
    print(f"Type: {opp.opportunity_type.value}")
    print(f"Description: {opp.description}")
    print()
```

## Configuration

Create a `.env` file:
```bash
POLYMARKET_API_KEY=your_key_here
MIN_PROFIT_THRESHOLD=1.0
MAX_TOTAL_PRICE_THRESHOLD=0.98
```

Then use:
```python
from polyarb.config import Config

config = Config()
min_profit = config.get("min_profit_threshold", 1.0)
```

## Adding New Platforms

See `examples/add_custom_platform.py` for a complete tutorial.

Quick version:
```python
from polyarb.platforms.base import PlatformInterface, Market

class MyPlatform(PlatformInterface):
    @property
    def platform_name(self) -> str:
        return "MyPlatform"
    
    def get_markets(self, limit=None):
        # Fetch from your API
        return [Market(...)]
    
    def get_market(self, market_id):
        # Fetch single market
        return Market(...)
```

## Project Structure

```
polyarb/
├── polyarb/              # Main package
│   ├── core/            # Arbitrage engine & opportunity models
│   ├── platforms/       # Platform integrations
│   └── config.py        # Configuration management
├── examples/            # Usage examples
├── tests/              # Test suite
└── README.md           # Full documentation
```

## Two Types of Arbitrage

### Intra-Platform
When sum of outcome prices < 1, buy all outcomes for guaranteed profit.

Example: Yes=$0.45, No=$0.50 → Total=$0.95 → Profit=5.26%

### Cross-Platform
When same market has different prices across platforms.

Example: Platform A: Yes=$0.60, Platform B: Yes=$0.72 → Profit=20%

## Support

See README.md for full documentation.
