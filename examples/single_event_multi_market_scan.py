"""
Opt-in research scan against public Polymarket data.

This example fetches active events from the public Polymarket Gamma API, keeps
markets that expose YES token IDs, and scans them for single-event, multi-market
model-implied basket edges when an "other" option appears to complete the outcome
space. It does not validate contract equivalence or resolution rules and does not
approve, simulate, or submit orders.
"""

import argparse
import asyncio
import json
from typing import Any, Dict, List

import requests

from polyarb.data.clob_client import CLOBClient
from polyarb.data.price_accessor import PriceAccessor
from polyarb.data.models import PriceType
from polyarb.scanner import SingleEventMultiMarketScanner


GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"


def _parse_gamma_array(value: Any) -> List[Any]:
    """Return a Gamma array from either its JSON-string or list representation."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    return value if isinstance(value, list) else []


def _normalize_outcomes(market: Dict[str, Any]) -> List[Dict[str, str]]:
    """Pair current Gamma outcome labels with their corresponding CLOB token IDs."""
    raw_outcomes = _parse_gamma_array(market.get("outcomes"))
    if not raw_outcomes:
        return []

    # Retain compatibility with the earlier dictionary representation.
    if all(isinstance(outcome, dict) for outcome in raw_outcomes):
        normalized = []
        for outcome in raw_outcomes:
            token_id = outcome.get("tokenId") or outcome.get("yesTokenId")
            if token_id:
                normalized.append(
                    {
                        "label": str(outcome.get("name") or outcome.get("label") or "Yes"),
                        "yes_token_id": str(token_id),
                    }
                )
        return normalized

    token_ids = _parse_gamma_array(market.get("clobTokenIds"))
    if len(raw_outcomes) != len(token_ids):
        return []

    return [
        {"label": str(label), "yes_token_id": str(token_id)}
        for label, token_id in zip(raw_outcomes, token_ids)
        if label is not None and token_id
    ]


def fetch_markets(limit: int = 200) -> List[Dict[str, Any]]:
    """Fetch markets with outcome token IDs from the Gamma API."""

    params = {
        "limit": limit,
        "active": "true",
        "closed": "false",
        "archived": "false",
    }

    response = requests.get(GAMMA_EVENTS_URL, params=params, timeout=15)
    response.raise_for_status()

    payload = response.json()
    events = payload.get("events") if isinstance(payload, dict) else payload
    if not isinstance(events, list):
        return []

    markets: List[Dict[str, Any]] = []
    for event in events:
        event_id = event.get("id")
        for market in event.get("markets") or []:
            outcomes = _normalize_outcomes(market)

            if not outcomes:
                continue

            markets.append(
                {
                    "id": market.get("id"),
                    "event_id": event_id,
                    "question": market.get("question") or market.get("title"),
                    "outcomes": outcomes,
                }
            )

    return markets


async def run_scan(limit: int, min_profit: float, max_total_price: float, price_type: PriceType):
    clob_client = CLOBClient()
    price_accessor = PriceAccessor(clob_client=clob_client)
    scanner = SingleEventMultiMarketScanner(
        price_accessor=price_accessor,
        min_profit_threshold=min_profit,
        max_total_price_threshold=max_total_price,
        price_type=price_type,
        fee_rate_bps=10.0,
        slippage_bps=10.0,
    )

    markets = fetch_markets(limit=limit)
    if not markets:
        print("No markets with token IDs were returned from the API.")
        return

    print(f"Scanning {len(markets)} markets for conditional model-implied edges...")
    result = await scanner.scan(markets)
    print(f"Scan complete in {result.scan_duration_ms:.0f} ms")

    if not result.opportunities:
        print("No opportunities found. Try increasing the limit or lowering thresholds.")
    else:
        for idx, opp in enumerate(result.opportunities, start=1):
            print()
            print(f"Detected candidate #{idx}: {opp.name}")
            print(f"  Event IDs: {', '.join(opp.event_ids)}")
            print(f"  Markets: {', '.join(opp.market_ids)}")
            print(f"  Quoted ASK Cost: {opp.total_cost:.4f}")
            print(f"  Model-implied edge: {opp.profit_percentage:.2f}%")
            print(f"  Spread-adjusted model edge: {opp.adjusted_profit_percentage:.2f}%")

    print("Detected candidates are not approved, submitted, filled, settled, or reported trades.")

    await clob_client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=200, help="Number of events to fetch")
    parser.add_argument(
        "--min-profit", type=float, default=0.5, help="Minimum model-edge percentage"
    )
    parser.add_argument(
        "--max-total-price",
        type=float,
        default=0.98,
        help="Maximum total YES cost before declaring no arbitrage",
    )
    parser.add_argument(
        "--price-type",
        type=str,
        default="ASK",
        choices=[PriceType.ASK.name],
        help="Buy-side pricing orientation; only ASK is supported",
    )

    args = parser.parse_args()
    asyncio.run(
        run_scan(
            limit=args.limit,
            min_profit=args.min_profit,
            max_total_price=args.max_total_price,
            price_type=PriceType[args.price_type],
        )
    )


if __name__ == "__main__":
    main()
