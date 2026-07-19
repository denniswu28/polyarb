"""Offline tests for UTF-8 and HTML reporting boundaries."""

from pathlib import Path

import pytest

from polyarb.reporting import (
    PerformanceMetrics,
    ReportGenerator,
    UnvalidatedLiveExecutionError,
)
from polyarb.scanner.enhanced_opportunity import (
    EnhancedOpportunity,
    OpportunityClass,
)


def test_opportunity_html_uses_utf8_and_escapes_external_text(tmp_path):
    opportunity = EnhancedOpportunity(
        id="report-1",
        opportunity_class=OpportunityClass.SINGLE_CONDITION,
        name='<script>alert("x")</script> – café',
        total_cost=0.9,
        expected_profit=0.1,
        profit_percentage=11.1,
    )
    generator = ReportGenerator(output_dir=str(tmp_path))

    path = generator.generate_opportunities_html(
        [opportunity],
        filename="report.html",
        title="Résumé <unsafe>",
    )
    rendered = Path(path).read_bytes().decode("utf-8")

    assert "Résumé &lt;unsafe&gt;" in rendered
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; – café" in rendered
    assert "<script>" not in rendered


def test_performance_html_escapes_dynamic_group_labels(tmp_path):
    metrics = PerformanceMetrics(
        by_opportunity_class={
            "<img src=x onerror=alert(1)>": {
                "count": 1,
                "total_profit": 0.1,
                "avg_profit_pct": 1.0,
            }
        },
        by_topic={
            "<script>topic</script>": {
                "count": 1,
                "total_profit": 0.1,
                "avg_profit_pct": 1.0,
            }
        },
    )
    generator = ReportGenerator(output_dir=str(tmp_path))

    path = generator.generate_performance_report(metrics, filename="metrics.html")
    rendered = Path(path).read_bytes().decode("utf-8")

    assert "&lt;img src=x onerror=alert(1)&gt;" in rendered
    assert "&lt;script&gt;topic&lt;/script&gt;" in rendered
    assert "<script>" not in rendered
    assert "Realized Result (No Validated Importer)" in rendered


def test_performance_report_rejects_caller_constructed_realized_metrics(tmp_path):
    generator = ReportGenerator(output_dir=str(tmp_path))
    metrics = PerformanceMetrics(
        submitted_executions=1,
        settled_executions=1,
        total_realized_profit=0.10,
    )

    with pytest.raises(UnvalidatedLiveExecutionError, match="cannot be reported"):
        generator.generate_performance_report(metrics, filename="fabricated.html")

    assert not (tmp_path / "fabricated.html").exists()
