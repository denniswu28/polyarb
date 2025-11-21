"""
Report generation for opportunities and performance.
"""

import csv
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from polyarb.scanner.enhanced_opportunity import EnhancedOpportunity
from polyarb.reporting.performance_tracker import PerformanceMetrics


class ReportGenerator:
    """
    Generates CSV and HTML reports for opportunities and performance.
    """
    
    def __init__(self, output_dir: str = "./reports"):
        """
        Initialize report generator.
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_opportunities_csv(
        self,
        opportunities: List[EnhancedOpportunity],
        filename: Optional[str] = None
    ) -> str:
        """
        Generate CSV report of opportunities.
        
        Args:
            opportunities: List of opportunities
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to generated file
        """
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"opportunities_{timestamp}.csv"
        
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                "ID",
                "Class",
                "Name",
                "Legs",
                "Total Cost",
                "Expected Profit",
                "Profit %",
                "Adjusted Profit %",
                "Risk Level",
                "Liquidity Score",
                "Max Size",
                "Markets",
                "Pure Arb",
                "Topic",
                "Discovered At"
            ])
            
            # Data rows
            for opp in opportunities:
                writer.writerow([
                    opp.id,
                    opp.opportunity_class.value,
                    opp.name,
                    len(opp.legs),
                    f"{opp.total_cost:.4f}",
                    f"{opp.expected_profit:.4f}",
                    f"{opp.profit_percentage:.2f}",
                    f"{opp.adjusted_profit_percentage:.2f}" if opp.adjusted_profit_percentage else "",
                    opp.risk_level.value,
                    f"{opp.liquidity_score:.2f}" if opp.liquidity_score else "",
                    f"{opp.max_size:.0f}" if opp.max_size else "",
                    len(opp.market_ids),
                    opp.is_pure_arbitrage,
                    opp.topic or "",
                    opp.discovered_at.isoformat()
                ])
        
        return str(filepath)
    
    def generate_opportunities_html(
        self,
        opportunities: List[EnhancedOpportunity],
        filename: Optional[str] = None,
        title: str = "Arbitrage Opportunities"
    ) -> str:
        """
        Generate HTML report of opportunities.
        
        Args:
            opportunities: List of opportunities
            filename: Output filename (auto-generated if None)
            title: Report title
            
        Returns:
            Path to generated file
        """
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"opportunities_{timestamp}.html"
        
        filepath = self.output_dir / filename
        
        # Sort by profit percentage
        sorted_opps = sorted(
            opportunities,
            key=lambda o: o.profit_percentage,
            reverse=True
        )
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
        }}
        .summary {{
            background: white;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .profit-high {{
            color: #2e7d32;
            font-weight: bold;
        }}
        .profit-medium {{
            color: #f57c00;
        }}
        .risk-low {{
            color: #2e7d32;
        }}
        .risk-medium {{
            color: #f57c00;
        }}
        .risk-high {{
            color: #c62828;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Opportunities:</strong> {len(opportunities)}</p>
        <p><strong>Generated:</strong> {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC</p>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>Class</th>
                <th>Name</th>
                <th>Legs</th>
                <th>Cost</th>
                <th>Profit %</th>
                <th>Adj. Profit %</th>
                <th>Risk</th>
                <th>Liquidity</th>
                <th>Pure Arb</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for opp in sorted_opps:
            profit_class = "profit-high" if opp.profit_percentage >= 2.0 else "profit-medium"
            risk_class = f"risk-{opp.risk_level.value}"
            
            html += f"""
            <tr>
                <td>{opp.opportunity_class.value}</td>
                <td>{opp.name[:50]}</td>
                <td>{len(opp.legs)}</td>
                <td>{opp.total_cost:.4f}</td>
                <td class="{profit_class}">{opp.profit_percentage:.2f}%</td>
                <td>{opp.adjusted_profit_percentage:.2f}% if opp.adjusted_profit_percentage else 'N/A'</td>
                <td class="{risk_class}">{opp.risk_level.value}</td>
                <td>{opp.liquidity_score:.2f if opp.liquidity_score else 'N/A'}</td>
                <td>{'✓' if opp.is_pure_arbitrage else '✗'}</td>
            </tr>
"""
        
        html += """
        </tbody>
    </table>
</body>
</html>
"""
        
        with open(filepath, 'w') as f:
            f.write(html)
        
        return str(filepath)
    
    def generate_performance_report(
        self,
        metrics: PerformanceMetrics,
        filename: Optional[str] = None
    ) -> str:
        """
        Generate HTML performance report.
        
        Args:
            metrics: Performance metrics
            filename: Output filename
            
        Returns:
            Path to generated file
        """
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_{timestamp}.html"
        
        filepath = self.output_dir / filename
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Performance Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .section {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1, h2 {{
            color: #333;
        }}
        .metric {{
            display: inline-block;
            margin: 10px 20px 10px 0;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
        }}
        .metric-label {{
            font-size: 14px;
            color: #666;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f0f0f0;
        }}
    </style>
</head>
<body>
    <h1>Performance Report</h1>
    
    <div class="section">
        <h2>Overview</h2>
        <div class="metric">
            <div class="metric-value">{metrics.total_opportunities}</div>
            <div class="metric-label">Total Opportunities</div>
        </div>
        <div class="metric">
            <div class="metric-value">{metrics.executed_opportunities}</div>
            <div class="metric-label">Executed</div>
        </div>
        <div class="metric">
            <div class="metric-value">{metrics.successful_executions}</div>
            <div class="metric-label">Successful</div>
        </div>
        <div class="metric">
            <div class="metric-value">{metrics.hit_rate:.1%}</div>
            <div class="metric-label">Hit Rate</div>
        </div>
    </div>
    
    <div class="section">
        <h2>Financial Metrics</h2>
        <div class="metric">
            <div class="metric-value">${metrics.total_theoretical_profit:.2f}</div>
            <div class="metric-label">Theoretical Profit</div>
        </div>
        <div class="metric">
            <div class="metric-value">${metrics.total_realized_profit:.2f}</div>
            <div class="metric-label">Realized Profit</div>
        </div>
        <div class="metric">
            <div class="metric-value">{metrics.avg_profit_percentage:.2f}%</div>
            <div class="metric-label">Avg Profit %</div>
        </div>
        <div class="metric">
            <div class="metric-value">{metrics.avg_slippage_bps:.1f}</div>
            <div class="metric-label">Avg Slippage (bps)</div>
        </div>
    </div>
    
    <div class="section">
        <h2>By Opportunity Class</h2>
        <table>
            <tr>
                <th>Class</th>
                <th>Count</th>
                <th>Total Profit</th>
                <th>Avg Profit %</th>
            </tr>
"""
        
        for opp_class, data in metrics.by_opportunity_class.items():
            html += f"""
            <tr>
                <td>{opp_class}</td>
                <td>{data['count']}</td>
                <td>${data['total_profit']:.2f}</td>
                <td>{data['avg_profit_pct']:.2f}%</td>
            </tr>
"""
        
        html += """
        </table>
    </div>
    
    <div class="section">
        <h2>By Topic</h2>
        <table>
            <tr>
                <th>Topic</th>
                <th>Count</th>
                <th>Total Profit</th>
                <th>Avg Profit %</th>
            </tr>
"""
        
        for topic, data in metrics.by_topic.items():
            html += f"""
            <tr>
                <td>{topic}</td>
                <td>{data['count']}</td>
                <td>${data['total_profit']:.2f}</td>
                <td>{data['avg_profit_pct']:.2f}%</td>
            </tr>
"""
        
        html += """
        </table>
    </div>
</body>
</html>
"""
        
        with open(filepath, 'w') as f:
            f.write(html)
        
        return str(filepath)
