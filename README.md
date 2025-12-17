# Polyarb - Prediction Market Arbitrage Engine

An intelligent arbitrage detection system for prediction markets including Polymarket, PredictIt, and Kalshi. Polyarb identifies both intra-platform and cross-platform arbitrage opportunities to maximize profit potential.

## Enhanced System Architecture

Beyond the core engine, the enhanced Polymarket system is organized into six modules that work together:

1. **Data, Market State & Storage** – SQLAlchemy models, order book accessors, and price abstractions for ASK/BID/MID/LIVE/ACTUAL.
2. **Strategy Template Library** – Reusable strategy builders (e.g., `all_no`, `balanced`) and a registry for filtering and discovery.
3. **Embedding & Dependency Detection** – Event embeddings, clustering, and LLM-based dependency detection for combinatorial arbitrage.
4. **Enhanced Arbitrage Scanner** – Single-condition, NegRisk, and strategy-aware scanners with liquidity-aware profitability scoring.
5. **Execution & Risk Management** – Basket execution, slippage tracking, and configurable risk limits across strategies and markets.
6. **Evaluation, Backtesting & Reporting** – Performance tracking, historical replay utilities, and CSV/HTML report generation.

See `ENHANCED_SYSTEM.md` for a full breakdown and walkthrough.

## Features

- 🎯 **Intra-Platform Arbitrage**: Detect opportunities within a single platform where the sum of outcome prices is less than 1
- 🔄 **Cross-Platform Arbitrage**: Identify price discrepancies for the same markets across different platforms
- 🏗️ **Modular Architecture**: Easily extend with new platform integrations
- ⚙️ **Configurable**: Customize profit thresholds, refresh intervals, and more
- 🔌 **Platform Support**:
  - ✅ Polymarket (implemented)
  - 🚧 PredictIt (framework ready)
  - 🚧 Kalshi (framework ready)

## Installation

```bash
# Clone the repository
git clone https://github.com/denniswu28/polyarb.git
cd polyarb

# Install dependencies
pip install -r requirements.txt

# For development
pip install -r requirements-dev.txt
```

## Quick Start

```python
from polyarb import ArbitrageEngine
from polyarb.platforms.polymarket import PolymarketPlatform

# Initialize platform
polymarket = PolymarketPlatform()

# Create arbitrage engine
engine = ArbitrageEngine(
    platforms=[polymarket],
    min_profit_threshold=1.0  # 1% minimum profit
)

# Find opportunities
opportunities = engine.find_opportunities()

# Display results
for opp in opportunities:
    print(f"Profit: {opp.profit_percentage:.2f}%")
    print(f"Strategy: {opp.description}")
```

## Usage Examples

### Basic Usage

Run the included example to see the engine in action:

```bash
python examples/basic_usage.py
```

### Configuration

Create a `.env` file in the project root (see `.env.example`):

```bash
# Optional API keys
POLYMARKET_API_KEY=your_key_here

# Engine settings
MIN_PROFIT_THRESHOLD=1.0
MAX_TOTAL_PRICE_THRESHOLD=0.98
REFRESH_INTERVAL=60
```

### Custom Integration

```python
from polyarb.config import Config
from polyarb import ArbitrageEngine
from polyarb.platforms.polymarket import PolymarketPlatform

# Load configuration
config = Config()

# Initialize with custom settings
engine = ArbitrageEngine(
    platforms=[PolymarketPlatform()],
    min_profit_threshold=config.get("min_profit_threshold", 1.0),
    max_total_price_threshold=config.get("max_total_price_threshold", 0.98)
)

# Find and filter opportunities
opportunities = engine.find_opportunities()
high_confidence_opps = [o for o in opportunities if o.confidence > 0.9]
```

## Project Structure

```
polyarb/
├── polyarb/
│   ├── __init__.py           # Package entry point
│   ├── config.py             # Configuration management
│   ├── core/
│   │   ├── arbitrage_engine.py  # Main arbitrage detection logic
│   │   └── opportunity.py       # Opportunity data structures
│   └── platforms/
│       ├── base.py              # Base platform interface
│       └── polymarket.py        # Polymarket integration
├── examples/
│   └── basic_usage.py        # Usage examples
├── tests/                    # Test suite
├── requirements.txt          # Core dependencies
├── requirements-dev.txt      # Development dependencies
└── pyproject.toml           # Project configuration
```

## How It Works

### Intra-Platform Arbitrage

In an efficient market, the sum of probabilities (prices) for all outcomes should equal 1. When this sum is less than 1, you can buy all outcomes and guarantee a profit:

```
Market: "Will it rain tomorrow?"
- Yes: $0.45
- No: $0.50
- Total: $0.95

Strategy: Buy both outcomes for $0.95, guaranteed return of $1.00
Profit: $0.05 (5.26% return)
```

### Cross-Platform Arbitrage

When the same market exists on multiple platforms with different prices, you can buy low on one platform and sell high on another:

```
Market: "Will candidate X win?"
- Platform A: Yes at $0.55
- Platform B: Yes at $0.65

Strategy: Buy on Platform A, sell on Platform B
Profit: $0.10 per share (18.2% return)
```

## Extending to New Platforms

To add a new platform (e.g., PredictIt):

1. Create a new file in `polyarb/platforms/`:

```python
from polyarb.platforms.base import PlatformInterface, Market

class PredictItPlatform(PlatformInterface):
    @property
    def platform_name(self) -> str:
        return "PredictIt"
    
    def get_markets(self, limit=None):
        # Implement API integration
        pass
    
    def get_market(self, market_id):
        # Implement single market fetch
        pass
```

2. Add it to the engine:

```python
from polyarb.platforms.predictit import PredictItPlatform

engine = ArbitrageEngine(platforms=[
    PolymarketPlatform(),
    PredictItPlatform()
])
```

## Development

```bash
# Run tests
pytest

# Format code
black polyarb/

# Lint code
ruff check polyarb/
```

## Roadmap

- [x] Core arbitrage detection engine
- [x] Polymarket integration
- [x] Intra-platform arbitrage detection
- [x] Cross-platform arbitrage detection
- [ ] PredictIt integration
- [ ] Kalshi integration
- [ ] Real-time monitoring and alerts
- [ ] Web dashboard
- [ ] Automated execution (with user approval)
- [ ] Historical analysis and backtesting

## Disclaimer

This software is for educational and research purposes only. Arbitrage trading involves risk, and you should:

- Understand the platforms' terms of service
- Consider transaction fees and execution delays
- Be aware of market liquidity constraints
- Never invest more than you can afford to lose

The authors are not responsible for any financial losses incurred while using this software.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.