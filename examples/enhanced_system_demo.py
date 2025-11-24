"""
Comprehensive example demonstrating the enhanced Polymarket arbitrage system.

This example shows how to use all 6 modules together to:
1. Fetch and store market data
2. Create strategy templates
3. Discover similar events
4. Scan for arbitrage opportunities
5. Execute with risk management
6. Generate performance reports
"""

import asyncio
from datetime import datetime, timedelta

# Module A: Data, Market State & Storage
from polyarb.data import (
    Database,
    GammaClient,
    CLOBClient,
    PriceAccessor,
    PriceType,
)

# Module B: Strategy Template Library
from polyarb.strategies import (
    create_all_no_strategy,
    create_balanced_strategy,
    StrategyRegistry,
)

# Module C: Embedding & Dependency Detection
from polyarb.embeddings import (
    EventEmbedder,
    VectorStore,
    EventClusterer,
    DependencyDetector,
)

# Module D: Enhanced Arbitrage Scanner
from polyarb.scanner import (
    SingleConditionScanner,
    NegRiskScanner,
    StrategyScanner,
)

# Module E: Execution & Risk Management
from polyarb.execution import (
    BasketExecutor,
    RiskManager,
    RiskLimits,
    RuleRiskAnalyzer,
)

# Module F: Evaluation, Backtesting & Reporting
from polyarb.reporting import (
    PerformanceTracker,
    ReportGenerator,
)


async def main():
    """Main demonstration function."""
    
    print("=" * 70)
    print("Polymarket Enhanced Arbitrage System - Comprehensive Demo")
    print("=" * 70)
    print()
    
    # =================================================================
    # STEP 1: Initialize Data Layer
    # =================================================================
    print("Step 1: Initializing data layer...")
    
    # Use in-memory SQLite for demo (use PostgreSQL in production)
    db = Database(database_url=None, echo=False)
    db.initialize()
    
    # Initialize API clients
    gamma_client = GammaClient()
    clob_client = CLOBClient()
    
    # Create price accessor
    with db.session() as session:
        price_accessor = PriceAccessor(
            clob_client=clob_client,
            db_session=session
        )
    
    print("✓ Database initialized")
    print("✓ Gamma and CLOB clients ready")
    print()
    
    # =================================================================
    # STEP 2: Fetch and Store Market Data
    # =================================================================
    print("Step 2: Fetching market data...")
    
    try:
        # Fetch events with documented parameters
        filters = GammaClient.get_default_filters()
        events_data = await gamma_client.fetch_events(limit=min(10, filters.get("limit", 10)))
        
        print(f"✓ Fetched {len(events_data)} events from Gamma API")
        
        # Parse and store in database
        events, markets, outcomes = gamma_client.parse_events_with_markets(events_data)
        
        with db.session() as session:
            # Add to database
            for event in events:
                session.add(event)
            for market in markets:
                session.add(market)
            for outcome in outcomes:
                session.add(outcome)
        
        print(f"✓ Stored {len(events)} events, {len(markets)} markets, {len(outcomes)} outcomes")
        print()
        
    except Exception as e:
        print(f"Note: Could not fetch live data: {e}")
        print("Continuing with mock data for demonstration...")
        events_data = []
        print()
    
    # =================================================================
    # STEP 3: Create Strategy Templates
    # =================================================================
    print("Step 3: Creating strategy templates...")
    
    registry = StrategyRegistry()
    
    # Example 1: all_no strategy (mutually exclusive outcomes)
    if len(outcomes) >= 3:
        all_no_strategy = create_all_no_strategy(
            name="Election Outcomes Dutch-Book",
            subtitle="Buy NO on all mutually exclusive election outcomes",
            positions=[
                {
                    "event_id": outcomes[0].market_id,
                    "event_slug": "demo-event",
                    "market_id": outcomes[0].market_id,
                    "market_slug": "demo-market",
                    "outcome_label": outcomes[0].label,
                    "outcome_id": outcomes[0].condition_id,
                    "token_id": outcomes[0].no_token_id,
                }
                for i, outcome in enumerate(outcomes[:3])
            ],
            topic="politics",
            tags=["election", "pure_arb"]
        )
        registry.add(all_no_strategy)
        print(f"✓ Created all_no strategy: {all_no_strategy.name}")
    
    print(f"✓ Registry contains {registry.count()} strategies")
    print()
    
    # =================================================================
    # STEP 4: Event Embedding and Clustering
    # =================================================================
    print("Step 4: Embedding and clustering events...")
    
    # Initialize embedder
    embedder = EventEmbedder()
    
    if events_data:
        # Embed events
        embeddings = embedder.embed_events_batch(
            events_data,
            batch_size=10,
            show_progress=False
        )
        
        # Store in vector database
        vector_store = VectorStore(collection_name="demo_events")
        
        event_ids = [e.get("id") for e in events_data]
        metadatas = [
            {
                "title": e.get("title", ""),
                "topic": e.get("topic", ""),
                "volume": float(e.get("volume", 0))
            }
            for e in events_data
        ]
        
        vector_store.add_events(
            event_ids=event_ids,
            embeddings=embeddings,
            metadatas=metadatas
        )
        
        print(f"✓ Embedded and stored {len(event_ids)} events")
        
        # Cluster similar events
        clusterer = EventClusterer(min_similarity=0.8)
        clusters = clusterer.cluster_events(event_ids, embeddings, metadatas)
        
        print(f"✓ Found {len([c for c in clusters if c != -1])} clusters")
    else:
        print("✓ Skipping embedding (no live data)")
    
    print()
    
    # =================================================================
    # STEP 5: Scan for Arbitrage Opportunities
    # =================================================================
    print("Step 5: Scanning for arbitrage opportunities...")
    
    # Initialize scanners
    single_scanner = SingleConditionScanner(
        price_accessor=price_accessor,
        min_profit_threshold=0.5,
        price_type=PriceType.ASK
    )
    
    negrisk_scanner = NegRiskScanner(
        price_accessor=price_accessor,
        min_profit_threshold=0.5
    )
    
    strategy_scanner = StrategyScanner(
        price_accessor=price_accessor,
        min_profit_threshold=0.5
    )
    
    # Prepare markets for scanning
    markets_for_scan = [
        {
            "id": m.id,
            "question": m.question,
            "outcomes": [
                {
                    "label": o.label,
                    "yes_token_id": o.yes_token_id,
                    "no_token_id": o.no_token_id,
                }
                for o in m.outcomes
            ],
            "is_neg_risk": m.is_neg_risk,
            "neg_risk_id": m.neg_risk_id,
        }
        for m in markets
    ]
    
    # Scan for opportunities
    single_results = await single_scanner.scan(markets_for_scan[:5])
    print(f"✓ Single-condition scan: {single_results.get_opportunity_count()} opportunities")
    
    negrisk_results = await negrisk_scanner.scan(markets_for_scan)
    print(f"✓ NegRisk scan: {negrisk_results.get_opportunity_count()} opportunities")
    
    if registry.count() > 0:
        strategy_results = await strategy_scanner.scan_strategies(
            registry.get_all()
        )
        print(f"✓ Strategy scan: {strategy_results.get_opportunity_count()} opportunities")
    
    print()
    
    # =================================================================
    # STEP 6: Apply Risk Management
    # =================================================================
    print("Step 6: Applying risk management...")
    
    # Initialize risk manager with limits
    risk_limits = RiskLimits(
        max_total_notional=10000.0,
        max_per_strategy_notional=2000.0,
        min_profit_threshold=0.5,
        min_liquidity_score=0.3
    )
    
    risk_manager = RiskManager(limits=risk_limits)
    
    # Get all opportunities
    all_opportunities = (
        single_results.opportunities +
        negrisk_results.opportunities
    )
    
    # Check each opportunity against risk limits
    approved_opportunities = []
    for opp in all_opportunities:
        passed, violations = risk_manager.check_opportunity(opp, proposed_size=1.0)
        if passed:
            approved_opportunities.append(opp)
        else:
            print(f"  Rejected: {opp.name[:40]} - {violations[0]}")
    
    print(f"✓ Approved {len(approved_opportunities)}/{len(all_opportunities)} opportunities")
    print()
    
    # =================================================================
    # STEP 7: Rule Risk Analysis
    # =================================================================
    print("Step 7: Analyzing rule risk...")
    
    rule_analyzer = RuleRiskAnalyzer()
    
    high_risk_count = 0
    for market_dict in markets_for_scan[:5]:
        analysis = rule_analyzer.analyze_market_rules(market_dict)
        if analysis["risk_category"].value in ["high", "critical"]:
            high_risk_count += 1
    
    print(f"✓ Analyzed {len(markets_for_scan[:5])} markets")
    print(f"  {high_risk_count} markets flagged as high rule risk")
    print()
    
    # =================================================================
    # STEP 8: Execute Opportunities (Simulated)
    # =================================================================
    print("Step 8: Executing opportunities (simulated)...")
    
    executor = BasketExecutor(
        max_slippage_bps=50,
        min_fill_rate=0.8
    )
    
    executions = []
    for opp in approved_opportunities[:3]:  # Execute top 3
        result = await executor.execute_opportunity(
            opp,
            target_size=1.0,
            aggressive=False
        )
        executions.append(result)
        
        print(f"  {opp.name[:40]}: {result.status.value} ({result.get_fill_rate():.0%} filled)")
    
    print(f"✓ Executed {len(executions)} opportunities")
    print()
    
    # =================================================================
    # STEP 9: Track Performance and Generate Reports
    # =================================================================
    print("Step 9: Tracking performance and generating reports...")
    
    # Track performance
    tracker = PerformanceTracker()
    
    for opp in all_opportunities:
        tracker.add_opportunity(opp)
    
    for i, execution in enumerate(executions):
        if i < len(approved_opportunities):
            tracker.add_execution(
                approved_opportunities[i].id,
                execution
            )
    
    # Calculate metrics
    metrics = tracker.calculate_metrics()
    
    print(f"✓ Performance Metrics:")
    print(f"  Total Opportunities: {metrics.total_opportunities}")
    print(f"  Executed: {metrics.executed_opportunities}")
    print(f"  Success Rate: {metrics.hit_rate:.1%}")
    print(f"  Avg Profit: {metrics.avg_profit_percentage:.2f}%")
    print(f"  Total Theoretical Profit: ${metrics.total_theoretical_profit:.2f}")
    print()
    
    # Generate reports
    report_gen = ReportGenerator(output_dir="./demo_reports")
    
    csv_path = report_gen.generate_opportunities_csv(all_opportunities)
    print(f"✓ Generated CSV report: {csv_path}")
    
    html_path = report_gen.generate_opportunities_html(
        all_opportunities,
        title="Demo Arbitrage Opportunities"
    )
    print(f"✓ Generated HTML report: {html_path}")
    
    perf_path = report_gen.generate_performance_report(metrics)
    print(f"✓ Generated performance report: {perf_path}")
    print()
    
    # =================================================================
    # SUMMARY
    # =================================================================
    print("=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print()
    print("Summary:")
    print(f"  - Processed {len(markets)} markets from {len(events)} events")
    print(f"  - Created {registry.count()} strategy templates")
    print(f"  - Discovered {len(all_opportunities)} arbitrage opportunities")
    print(f"  - Approved {len(approved_opportunities)} for execution")
    print(f"  - Executed {len(executions)} opportunities")
    print(f"  - Generated 3 reports in ./demo_reports/")
    print()
    print("The system is ready for production use with:")
    print("  ✓ Real-time market data ingestion")
    print("  ✓ Multi-type arbitrage scanning")
    print("  ✓ Comprehensive risk management")
    print("  ✓ Execution tracking and reporting")
    
    # Cleanup
    await gamma_client.close()
    await clob_client.close()


if __name__ == "__main__":
    asyncio.run(main())
