"""
Run the SingleEventMultiMarketScanner against live Polymarket data.

This example fetches active events from the public Polymarket Gamma API, keeps
markets that expose YES token IDs, and scans them for single-event, multi-market
arbitrage when an "other" option completes the outcome space.
"""

import argparse
import asyncio
from typing import Any, Dict, List

import requests

from polyarb.data.clob_client import CLOBClient
from polyarb.data.price_accessor import PriceAccessor
from polyarb.data.models import PriceType
from polyarb.scanner import SingleEventMultiMarketScanner


GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"


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
            # Extract YES token IDs from the outcome entries. Gamma responses use
            # "tokenId" or "yesTokenId" depending on the market type.
            outcomes = []
            for outcome in market.get("outcomes") or []:
                yes_token_id = outcome.get("tokenId") or outcome.get("yesTokenId")
                if not yes_token_id:
                    continue

                outcomes.append(
                    {
                        "label": outcome.get("name") or outcome.get("label") or "Yes",
                        "yes_token_id": yes_token_id,
                    }
                )

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
    )

    markets = fetch_markets(limit=limit)
    if not markets:
        print("No markets with token IDs were returned from the API.")
        return

    print(f"Scanning {len(markets)} markets for single-event multi-market arbitrage...")
    result = await scanner.scan(markets)
    print(f"Scan complete in {result.scan_duration_ms:.0f} ms")

    if not result.opportunities:
        print("No opportunities found. Try increasing the limit or lowering thresholds.")
    else:
        for idx, opp in enumerate(result.opportunities, start=1):
            print()
            print(f"Opportunity #{idx}: {opp.name}")
            print(f"  Event IDs: {', '.join(opp.event_ids)}")
            print(f"  Markets: {', '.join(opp.market_ids)}")
            print(f"  Total Cost: {opp.total_cost:.4f}")
            print(f"  Profit %: {opp.profit_percentage:.2f}%")
            print(f"  Adjusted Profit %: {opp.adjusted_profit_percentage:.2f}%")

    await clob_client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=200, help="Number of events to fetch")
    parser.add_argument(
        "--min-profit", type=float, default=0.5, help="Minimum profit percentage threshold"
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
        choices=[pt.name for pt in PriceType],
        help="Price type to use for pricing legs",
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
