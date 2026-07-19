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

## Liquidity and partial fills

Displayed ask depth constrains modeled size but is not a fill guarantee. Simulated
fill ratios and slippage are explicit deterministic inputs. A partial or cancelled
simulation must not be treated as a platform fill or cancellation.

## Cross-venue comparison

Question-text matching is only a coarse candidate generator. It does not establish
contract identity, settlement equivalence, jurisdiction/eligibility, the ability
to sell or short, transferability, or atomic execution. PredictIt and Kalshi
adapters are not implemented or validated.

## Historical and empirical claims

Historical replay, fill modeling against archived books, settlement ingestion,
and backtesting are not implemented. No Sharpe ratio, hit rate, return, profit,
deployment, or live-trading result is supported by this repository.
