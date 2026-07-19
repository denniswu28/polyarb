# Methodology and limitations

## Candidate arithmetic

For a long-only basket with quoted ASK cost \(C\), configured fee rate \(f\),
configured slippage rate \(s\), and asserted worst-case payoff \(P\), the scanner uses:

\[
C_{effective}=C\left(1+\frac{f+s}{10{,}000}\right),\qquad
edge=P-C_{effective}.
\]

The percentage field is `edge / C_effective`. It is a model output, not a trade,
forecast, performance result, or profit claim.

## Required assumptions

- Outcome tokens and their YES/NO orientation are correctly mapped.
- Contracts in a basket are mutually exclusive and exhaustive when the strategy
  requires those properties.
- Platform resolution rules deliver the asserted payoff in every modeled state.
- ASK quotes and displayed sizes are current and executable for the proposed size.
- Fee, slippage, transfer, funding, cancellation, and settlement assumptions are complete.

The scanner cannot prove these assumptions. Missing, malformed, reference-only,
or wrong-side prices fail closed in supported long-only scanners.

For single-event and NegRisk coverage baskets, every listed market is a required
leg. If any required outcome, token ID, market ID, or executable ASK quote is
missing, the entire group is rejected; the scanner never computes a candidate
from the remaining subset.

The public Gamma adapter stores `outcomePrices` as reference/display prices.
Those values may reflect a midpoint or last trade and are never promoted to an
executable ask or bid. Core-engine `Market` inputs must explicitly provide
order-book `asks` and `bids` with `price_semantics="executable"`; buys use asks
and sells use bids.

See Polymarket's [price and order-book semantics](https://docs.polymarket.com/concepts/prices-orderbook)
for the display-price distinction. Public Gamma reads do not require credentials;
authenticated CLOB operations use a separate signing and header model described
in the [API overview](https://docs.polymarket.com/api-reference/introduction) and
[authentication documentation](https://docs.polymarket.com/api-reference/authentication).
The `LIVE` reference-price accessor uses the unauthenticated public
[`/last-trade-price`](https://docs.polymarket.com/api-reference/market-data/get-last-trade-price)
endpoint; last trade remains reference data and is rejected as a buy-side
executable quote.

## Liquidity and partial fills

Displayed ask depth constrains modeled size but is not a fill guarantee. Simulated
fill ratios and slippage are explicit deterministic inputs. A partial or cancelled
simulation must not be treated as a platform fill or cancellation.

Simulation requires an active reservation from the same `RiskManager` that
approved the opportunity. Approval records an immutable fingerprint of the exact
size plus all leg, price, cost, market, strategy, risk, liquidity, and expiry
inputs. Any post-approval change invalidates execution. Directly changing an
opportunity's lifecycle flag does not authorize simulation, and releasing a
reservation revokes the approval.

## Cross-venue comparison

Question-text matching is only a coarse candidate generator. It does not establish
contract identity, settlement equivalence, jurisdiction/eligibility, the ability
to sell or short, transferability, or atomic execution. PredictIt and Kalshi
adapters are not implemented or validated.

## Historical and empirical claims

Historical replay, fill modeling against archived books, settlement ingestion,
and backtesting are not implemented. No Sharpe ratio, hit rate, return, profit,
deployment, or live-trading result is supported by this repository.

Because settlement ingestion is absent, reporting rejects direct or mutated
live, submitted, filled, cancelled, or settled objects. Realized-result fields
remain zero rather than trusting caller-constructed evidence.
