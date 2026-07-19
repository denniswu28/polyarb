# polyarb

`polyarb` is a prediction-market research and opportunity-scanning framework.
Its public, reproducible path uses deterministic synthetic data and simulated
execution only. This code has never submitted a real order.

Scanner output is a model-implied candidate, not evidence of an approved,
submitted, filled, settled, profitable, or legally permissible trade. No public
performance or profit claim is made.

## Evidence status

| Surface | Status | Evidence boundary |
| --- | --- | --- |
| Core synthetic market scanning | Implemented and tested | Offline intra-venue baskets use explicit synthetic asks; cross-venue comparisons use asks for buys and bids for sells |
| Polymarket parsing and public-data scanning | Implemented; owner-validated | Gamma display prices are labeled reference-only; the opt-in CLOB scanner obtains order-book quotes and is excluded from CI |
| Price orientation | Implemented and tested | Core and enhanced long-only scanners require executable ASK costs; BID/MID/LIVE/ACTUAL/reference inputs fail closed for buys |
| Fees, slippage, liquidity, and risk inputs | Implemented and tested | Simulations require an active manager-issued reservation whose immutable approval fingerprint and exact size still match |
| Basket execution | Simulated only | Deterministic paper fills; no order IDs, credentials, wallet, funded account, or submission |
| Research reporting | Implemented with boundaries | Simulations are excluded from submitted, filled, settled, and realized-result counts; unvalidated live/fill/settlement objects are rejected |
| SQL storage and optional embedding modules | Experimental | Module surfaces exist; not exercised by the default example or full end-to-end CI |
| Rule/dependency analysis | Experimental/placeholder | Heuristic framework; no validated LLM integration |
| PredictIt | Not implemented or validated | Adapter fails closed with `NotImplementedError` |
| Kalshi | Not implemented or validated | Adapter fails closed with `NotImplementedError` |
| Automated live execution | Intentionally unavailable | Live mode raises before credentials, wallets, or network order clients are consulted |
| Historical backtesting | Not implemented or validated | Compatibility API fails closed; no historical replay or performance result |
| Dashboard, database service, alerts, live monitoring | Planned/not implemented | No implementation claim |

Dennis reports validating Polymarket data/scanning and authentication/order-related
paths without submitting a real order. PredictIt and Kalshi behavior has not been
validated. See [PROVENANCE.md](PROVENANCE.md) for the owner and agent-contribution
record.

## Lifecycle vocabulary

The code and reports keep these states distinct:

| State | Meaning |
| --- | --- |
| `detected` | A scanner found a model-implied candidate |
| `approved` | Configured research/risk checks passed; no order exists |
| `simulated` | A deterministic paper-fill scenario ran; no order exists |
| `submitted` | A real order was sent to a platform (unsupported in this repository) |
| `filled` / `partially_filled` | A submitted order received real fills (unsupported) |
| `cancelled` | A submitted order was cancelled, or a simulation modeled a no-fill; the mode remains explicit |
| `settled` | A filled contract has a recorded platform settlement (unsupported) |
| `reported` | A research record was emitted; reporting does not upgrade execution evidence |

## Reproduce the offline example

Python 3.10, 3.11, and 3.12 are the documented versions and are exercised in
GitHub Actions. The same commands are used on Windows and Linux:

```bash
git clone https://github.com/denniswu28/polyarb.git
cd polyarb
python -m pip install .
python -m examples.demo_with_mock_data
```

The final command is deterministic, uses only committed synthetic fixtures, and
requires no network access, credentials, wallet, account, or private data.

For development:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m examples.demo_with_mock_data
```

Optional extras are installed explicitly:

```bash
python -m pip install -e ".[embeddings]"
python -m pip install -e ".[postgres]"
```

These extras are not necessary for the supported offline path.

## Minimal offline use

```python
from polyarb import ArbitrageEngine
from polyarb.platforms.base import Market

market = Market(
    id="synthetic-1",
    platform="SyntheticVenue",
    question="Synthetic binary outcome?",
    outcomes=["Yes", "No"],
    prices={"Yes": 0.45, "No": 0.50},
    metadata={
        "price_semantics": "executable",
        "asks": {"Yes": 0.45, "No": 0.50},
        "bids": {"Yes": 0.43, "No": 0.48},
    },
)

# A local test platform can expose this Market through PlatformInterface.
engine = ArbitrageEngine(fee_rate_bps=10, slippage_bps=10)
```

See [QUICKSTART.md](QUICKSTART.md) for a complete runnable command. Public
`examples/basic_usage.py` is a credential-free Gamma reference-data inspection.
`examples/single_event_multi_market_scan.py` is the opt-in public CLOB-quote
scanner. Neither network example is part of CI or the default reproduction claim.

## Methodology boundaries

- Long-only basket costs use ASK prices. BID is a sell price; MID and last-trade
  values are references, not executable buy costs.
- Gamma `outcomePrices` populate the backward-compatible display-price mapping
  only. They cannot produce an engine candidate without separately supplied
  executable order-book asks/bids.
- Candidate arithmetic assumes the selected contracts are mutually exclusive
  and exhaustive and that settlement rules deliver the modeled payoff. The
  scanner does not prove those assumptions.
- Single-event and NegRisk coverage scanners reject the entire group if any
  listed market lacks its required outcome, token ID, or executable ASK quote;
  they do not calculate a cheaper basket from a subset.
- Fees and slippage are explicit inputs. Displayed depth is a liquidity
  constraint, not a fill forecast.
- Cross-venue output is a quote-discrepancy research candidate. Contract
  equivalence, short/sell availability, transfer constraints, platform rules,
  and atomic execution are not established.
- A simulation is never included as submitted, filled, settled, or realized
  performance. Directly constructed live/fill/settlement records fail closed
  because no validated provenance-bearing importer exists. Historical
  backtesting is unavailable.

More detail is in [METHODOLOGY.md](METHODOLOGY.md).

## Data and execution safety

- Committed example data is deterministic synthetic/mock data only.
- Private account data, real trade records, credentials, wallet material,
  employer-derived content, proprietary content, and redistributed vendor
  datasets are excluded.
- Tests, CI, and the default example are offline after dependency installation.
- Live order submission is hard-disabled. `BasketExecutor` defaults to
  `ExecutionMode.SIMULATED`; live mode and `submit_live_order()` fail closed.
- `.env` and common generated/private outputs are ignored. Never commit secrets
  or account exports.

See [DATA_POLICY.md](DATA_POLICY.md), [SECURITY.md](SECURITY.md), and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Repository layout

```text
polyarb/
  core/        candidate arithmetic and lifecycle states
  data/        public-data clients, price access, optional SQL models
  scanner/     long-only research scanners
  execution/   risk checks and deterministic simulated fills
  reporting/   research reports; backtest API fails closed
  platforms/   Polymarket plus fail-closed PredictIt/Kalshi placeholders
examples/      offline default plus opt-in experimental/network examples
tests/         focused offline invariant and safety tests
```

## License and rules

The repository is MIT-licensed; see [LICENSE](LICENSE). Dependency license
metadata, example-origin review, and unresolved platform-term checks are recorded
in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Users remain responsible for
reviewing applicable law, eligibility, contract rules, and current platform terms.

This software is for research and education, not financial, legal, or investment advice.
