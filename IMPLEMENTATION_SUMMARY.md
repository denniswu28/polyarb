# Development surface and evidence summary

This file is a development record, not a completion, deployment, performance, or
production-readiness claim. The authoritative status matrix is in
[README.md](README.md).

## Demonstrated in the supported offline path

- Installable package on the Python versions exercised in GitHub Actions.
- Deterministic synthetic-data scan runnable with
  `python -m examples.demo_with_mock_data`.
- Core candidate arithmetic with explicit executable asks for buys, executable
  bids for sells, and fee/slippage inputs.
- ASK/BID orientation checks for long-only basket costs.
- Liquidity and configurable risk-limit checks with aggregate exposure and leg
  reservations that must remain active and exactly match their immutable
  approval-time fingerprint through simulated execution.
- Coverage scanners that reject an entire event/NegRisk group when any required
  outcome, token ID, or executable ASK quote is missing.
- Deterministic paper-fill scenarios, including partial/no-fill inputs, without
  order IDs or order submission.
- Reporting counters that separate detected, approved, simulated, submitted,
  filled, partially filled, cancelled, settled, and reported records while
  rejecting unvalidated live/fill/settlement objects.
- Fail-closed PredictIt, Kalshi, historical-backtest, and live-order paths.
- Offline tests, lint, and CI on Windows and Linux.

## Present but experimental

- SQLAlchemy models and optional PostgreSQL configuration.
- Embeddings, clustering, and vector-store modules behind optional dependencies.
- Strategy-template and heuristic rule/dependency analysis surfaces.
- CSV/HTML research report generation with UTF-8 output, HTML escaping, and
  neutralization of formula-leading external CSV text.
- Opt-in Polymarket public-API examples.

These surfaces are not demonstrated as an end-to-end system by the default
example. Their presence does not establish deployment safety, performance,
platform permission, contract equivalence, or live execution.

## Not implemented or not validated

- PredictIt and Kalshi integrations.
- Real-order creation, signing, submission, fill monitoring, cancellation, or
  settlement ingestion.
- Historical order-book replay and backtesting.
- Dashboard, alerts, embeddings service, database service, or live monitoring.
- Validated LLM dependency analysis.
- Public performance or profit results.

## Ownership and provenance

Dennis Wu states that `firefly` is his Git identity and that he personally
designed, implemented, and validated the components. Git history also contains
12 commits authored by `copilot-swe-agent[bot]`; they remain disclosed in
[PROVENANCE.md](PROVENANCE.md) and the repository history.

## Remaining review boundaries

Platform terms, optional dependency/transitive licenses, example origins, and
any future live-data use require continuing human review. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
[METHODOLOGY.md](METHODOLOGY.md).
