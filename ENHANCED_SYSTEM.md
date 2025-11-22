# Enhanced Polymarket Arbitrage System

A comprehensive, production-ready automated arbitrage system for Polymarket prediction markets.

## Overview

This enhanced system extends the basic polyarb framework with sophisticated features for Polymarket-specific arbitrage, including:

- **Multi-condition arbitrage**: YES/NO Dutch-books, NegRisk rebalancing
- **Strategy templates**: Reusable patterns like `all_no` and `balanced`
- **Event intelligence**: Embedding-based clustering and similarity search
- **Combinatorial arbitrage**: LLM-powered dependency detection between markets
- **Risk management**: Comprehensive position limits and rule risk analysis
- **Execution tracking**: Slippage monitoring and basket execution
- **Performance analytics**: Detailed reporting and backtesting

## Architecture

The system consists of 6 integrated modules:

### Module A: Data, Market State & Storage
- PostgreSQL/SQLite storage with SQLAlchemy ORM
- Gamma API client for events and markets
- CLOB API client for orderbooks and prices
- PriceAccessor supporting ASK/BID/MID/LIVE/ACTUAL price types
- Spread and liquidity metrics

### Module B: Strategy Template Library
- `all_no`: Dutch-book on mutually exclusive NO positions
- `balanced`: Two complementary position baskets
- `custom`: Arbitrary strategy templates
- Logical specification framework
- Strategy registry with filtering

### Module C: Embedding & Dependency Detection
- Event embedding with sentence transformers
- ChromaDB vector store for similarity search
- DBSCAN clustering for related events
- LLM-based market dependency detection
- Outcome table generation for combinatorial arb

### Module D: Enhanced Arbitrage Scanner
- SingleConditionScanner: YES/NO binary arbitrage
- NegRiskScanner: Within-market rebalancing
- StrategyScanner: Template-based opportunities
- Spread-adjusted profit calculation
- Liquidity scoring and ranking

### Module E: Execution & Risk Management
- BasketExecutor: Multi-leg execution with abort logic
- RiskManager: Position limits (total, per-strategy, per-market, per-topic)
- RuleRiskAnalyzer: LLM-based market rule analysis
- Slippage tracking
- Dynamic position sizing

### Module F: Evaluation, Backtesting & Reporting
- PerformanceTracker: Metrics by class, topic, price type
- ReportGenerator: CSV and HTML reports
- Backtester: Historical replay framework
- Price type comparison
- Dashboard utilities

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# For development
pip install -r requirements-dev.txt
```

### Basic Usage

```python
import asyncio
from polyarb.data import Database, GammaClient, CLOBClient, PriceAccessor, PriceType
from polyarb.scanner import SingleConditionScanner

async def main():
    # Initialize data layer
    db = Database()
    db.initialize()
    
    gamma_client = GammaClient()
    clob_client = CLOBClient()
    
    with db.session() as session:
        price_accessor = PriceAccessor(clob_client, session)
    
    # Fetch markets
    events_data = await gamma_client.fetch_events(limit=10)
    events, markets, outcomes = gamma_client.parse_events_with_markets(events_data)
    
    # Scan for arbitrage
    scanner = SingleConditionScanner(
        price_accessor=price_accessor,
        min_profit_threshold=0.5
    )
    
    markets_dict = [{"id": m.id, "outcomes": m.outcomes} for m in markets]
    results = await scanner.scan(markets_dict)
    
    print(f"Found {results.get_opportunity_count()} opportunities")
    
    # Cleanup
    await gamma_client.close()
    await clob_client.close()

asyncio.run(main())
```

### Run Complete Demo

```bash
python examples/enhanced_system_demo.py
```

## Configuration

### Database Setup

For production, use PostgreSQL:

```python
from polyarb.data import Database

db = Database(
    database_url="postgresql://user:password@localhost:5432/polyarb",
    pool_size=5,
    max_overflow=10
)
```

### Risk Limits

```python
from polyarb.execution import RiskLimits, RiskManager

limits = RiskLimits(
    max_total_notional=10000.0,
    max_per_strategy_notional=2000.0,
    max_per_market_notional=1000.0,
    min_profit_threshold=0.5,
    min_liquidity_score=0.3
)

risk_manager = RiskManager(limits=limits)
```

### Price Types

The system supports multiple price types:

- **ASK**: Lowest ask price (for buying)
- **BID**: Highest bid price (for selling)
- **MID**: Mid-market price `(bid + ask) / 2`
- **LIVE**: Last traded price (cached with TTL)
- **ACTUAL**: Actual execution price from trade history

```python
from polyarb.data import PriceType

# Use ASK prices for conservative estimates
scanner = SingleConditionScanner(
    price_accessor=price_accessor,
    price_type=PriceType.ASK
)
```

## Strategy Templates

### All NO Strategy

Buy NO on mutually exclusive outcomes:

```python
from polyarb.strategies import create_all_no_strategy

strategy = create_all_no_strategy(
    name="Election Outcomes Arb",
    subtitle="NO on all candidates",
    positions=[
        {
            "event_id": "event_1",
            "event_slug": "election-2024",
            "market_id": "market_1",
            "market_slug": "candidate-a-wins",
            "outcome_label": "Candidate A",
            "outcome_id": "condition_1",
            "token_id": "no_token_1"
        },
        # ... more positions
    ],
    topic="politics"
)
```

### Balanced Strategy

Two complementary baskets:

```python
from polyarb.strategies import create_balanced_strategy

strategy = create_balanced_strategy(
    name="Senate Control Hedge",
    subtitle="Cover all scenarios",
    side_a_positions=[...],  # Positions for outcome set A
    side_b_positions=[...],  # Positions for outcome set B
    worst_case_payoff=1.0,
    topic="politics"
)
```

## Performance Tracking

```python
from polyarb.reporting import PerformanceTracker, ReportGenerator

tracker = PerformanceTracker()

# Add opportunities
for opp in opportunities:
    tracker.add_opportunity(opp)

# Add executions
tracker.add_execution(opp_id, execution_result)

# Calculate metrics
metrics = tracker.calculate_metrics()

print(f"Total Profit: ${metrics.total_realized_profit:.2f}")
print(f"Hit Rate: {metrics.hit_rate:.1%}")
print(f"Avg Slippage: {metrics.avg_slippage_bps:.1f} bps")

# Generate reports
report_gen = ReportGenerator(output_dir="./reports")
report_gen.generate_opportunities_html(opportunities)
report_gen.generate_performance_report(metrics)
```

## Event Clustering

Find related markets using embeddings:

```python
from polyarb.embeddings import EventEmbedder, VectorStore, EventClusterer

# Embed events
embedder = EventEmbedder()
embeddings = embedder.embed_events_batch(events_data)

# Store in vector DB
vector_store = VectorStore(collection_name="events")
vector_store.add_events(event_ids, embeddings, metadatas)

# Query similar events
results = vector_store.query_similar(
    query_embedding,
    top_k=10,
    min_similarity=0.8
)

# Cluster events
clusterer = EventClusterer(min_similarity=0.8)
clusters = clusterer.cluster_events(event_ids, embeddings)
```

## Rule Risk Analysis

Analyze markets for resolution risk:

```python
from polyarb.execution import RuleRiskAnalyzer

analyzer = RuleRiskAnalyzer(llm_client=your_llm_client)

analysis = analyzer.analyze_market_rules(market)

print(f"Risk Category: {analysis['risk_category']}")
print(f"Risk Score: {analysis['risk_score']:.2f}")
print(f"Flags: {analysis['flags']}")
```

## API Reference

Detailed API documentation is available in each module:

- `polyarb.data.*` - Data layer and storage
- `polyarb.strategies.*` - Strategy templates
- `polyarb.embeddings.*` - Event intelligence
- `polyarb.scanner.*` - Arbitrage scanning
- `polyarb.execution.*` - Execution and risk
- `polyarb.reporting.*` - Analytics and reporting

## Development

### Running Tests

```bash
PYTHONPATH=/path/to/polyarb:$PYTHONPATH python -m pytest tests/ -v
```

### Code Formatting

```bash
black polyarb/
ruff check polyarb/
```

## Production Deployment

### Requirements

- PostgreSQL 12+
- Python 3.8+
- Sufficient API rate limits for Polymarket Gamma/CLOB APIs
- (Optional) OpenAI/Anthropic API for LLM features

### Best Practices

1. **Use PostgreSQL** for production storage
2. **Configure rate limiting** for API clients
3. **Set conservative risk limits** initially
4. **Monitor slippage** and adjust execution parameters
5. **Review rule risk** before executing high-value opportunities
6. **Enable logging** for debugging and audit trails
7. **Back up database** regularly
8. **Test with small positions** before scaling

### Environment Variables

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/polyarb
POLYMARKET_API_KEY=your_key_here
LLM_API_KEY=your_llm_key_here
MIN_PROFIT_THRESHOLD=0.5
MAX_TOTAL_NOTIONAL=10000
```

## Limitations

- **Non-atomic execution**: Multi-leg strategies face partial fill risk
- **No native shorting**: Limited to long-only positions (can use split/merge if available)
- **Rule risk**: Requires manual review of market rules
- **LLM dependency**: Some features require external LLM API
- **Historical data**: Backtesting requires orderbook snapshots

## Roadmap

- [ ] Real-time WebSocket orderbook streaming
- [ ] Automated Kelly sizing
- [ ] Multi-exchange support beyond Polymarket
- [ ] Advanced portfolio optimization
- [ ] Machine learning price prediction
- [ ] Automated rule parsing and classification

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## Disclaimer

This software is for educational and research purposes. Trading involves risk. The authors are not responsible for any financial losses. Always:

- Understand platform terms of service
- Consider transaction fees and execution delays
- Be aware of liquidity constraints
- Never invest more than you can afford to lose

## Support

For questions, issues, or feature requests, please open an issue on GitHub.
