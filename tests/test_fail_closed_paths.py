"""Negative tests for unvalidated platforms and placeholder features."""

from datetime import datetime

import pytest

from polyarb.platforms.kalshi import KalshiPlatform
from polyarb.platforms.predictit import PredictItPlatform
from polyarb.reporting import Backtester


@pytest.mark.parametrize("platform_class", [PredictItPlatform, KalshiPlatform])
def test_unvalidated_platforms_fail_closed(platform_class):
    platform = platform_class()

    with pytest.raises(NotImplementedError, match="not implemented or validated"):
        platform.initialize()
    with pytest.raises(NotImplementedError, match="not implemented or validated"):
        platform.get_markets()
    with pytest.raises(NotImplementedError, match="not implemented or validated"):
        platform.get_market("market")


def test_historical_backtest_fails_closed():
    backtester = Backtester()
    now = datetime.utcnow()

    with pytest.raises(NotImplementedError, match="not implemented or validated"):
        backtester.run_backtest(now, now, [])
    with pytest.raises(NotImplementedError, match="not implemented or validated"):
        backtester.compare_price_types([], ["ask"])
