"""Opt-in inspection of public Polymarket Gamma reference data.

This example contacts a public endpoint without credentials. Gamma display
prices are reference values, not executable bid/ask quotes, so the example
intentionally does not feed them to the arbitrage engine.
"""

from polyarb.platforms.polymarket import PolymarketPlatform


def main():
    """Fetch and label a small public Gamma reference-data sample."""
    print("=" * 60)
    print("Polyarb - opt-in Polymarket reference-data inspection")
    print("=" * 60)
    print()

    print("Preparing credential-free public-data client...")
    polymarket = PolymarketPlatform()
    print(f"- {polymarket.platform_name} client prepared")
    print()

    print("Fetching Gamma display/reference prices...")
    print("-" * 60)

    try:
        markets = polymarket.get_markets(limit=25)
    except Exception as exc:
        print("Public-data request failed due to an unexpected error.")
        print(f"  - Details: {exc}")
        raise

    print(f"Fetched {len(markets)} market record(s).")
    for market in markets[:5]:
        print(f"  - {market.question}: {market.prices}")

    print()
    print("=" * 60)
    print("Inspection complete. No candidate calculation or order action was performed.")
    print("Use CLOB asks for buys and CLOB bids for sells in executable-price analysis.")
    print("=" * 60)


if __name__ == "__main__":
    main()
