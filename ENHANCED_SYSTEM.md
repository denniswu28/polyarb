# Optional and experimental module guide

The modules below are research surfaces. They are not a production system and do
not enable live trading. Only the deterministic synthetic example and offline
test suite define the supported reproducibility path.

| Module | Current evidence | Important boundary |
| --- | --- | --- |
| Data and price access | SQL models, credential-free public-data clients, ASK/BID/MID/LIVE/ACTUAL accessors | Gamma display values are reference-only; only order-book ASK is accepted as a long-only executable buy cost; public live data is opt-in |
| Strategy templates | `all_no`, balanced, and custom data structures | Logical coverage and rule equivalence require independent review |
| Embeddings and dependencies | Optional embedding, clustering, vector-store, and heuristic/LLM interfaces | Experimental; no validated LLM pipeline or default offline evidence |
| Scanners | Single-condition, NegRisk, event-coverage, and template scanners | Coverage groups fail closed if any required outcome, token, or ASK is missing; candidate arithmetic is not approval or execution |
| Risk and execution | Configurable aggregate approval reservations and deterministic paper fills | Simulations require an unchanged immutable approval fingerprint and exact size; live submission is disabled |
| Reporting | Opportunity and research-metric exports | Simulations cannot contribute to submitted/filled/settled or realized-result fields; hand-built live records are rejected |
| Backtester | Compatibility class and result schema | `run_backtest` and price comparison fail closed; historical replay is not implemented |

## Install optional dependencies

```bash
python -m pip install -e ".[embeddings,postgres]"
```

Each extra is independent. The default install contains the dependencies needed
for the supported scanners, price access, simulation, reporting, and tests.

## Simulated execution

```python
from polyarb.execution import BasketExecutor, ExecutionMode, RiskManager

risk_manager = RiskManager()
approved, violations = risk_manager.approve_opportunity(opportunity, proposed_size=1.0)
if not approved:
    raise ValueError(violations)

executor = BasketExecutor(
    execution_mode=ExecutionMode.SIMULATED,
    risk_manager=risk_manager,
)

# A lifecycle flag alone is insufficient: the same RiskManager must retain the
# active reservation, and every fingerprinted field and the exact size must
# remain unchanged when the simulation starts.
# The result remains lifecycle_state="simulated" even when its hypothetical
# fill_status is "filled". No order ID is created.
result = await executor.execute_opportunity(
    opportunity,
    target_size=1.0,
    simulation_fill_ratios=[1.0, 0.5],
    simulation_slippage_bps=[5.0, 10.0],
)
```

Constructing a live-mode executor or calling `submit_live_order()` cannot submit
an order; execution raises `LiveExecutionDisabledError` before credentials,
wallets, or order-network code is used.

## Reporting boundary

`PerformanceTracker` retains older field names where needed for compatibility,
but their semantics are constrained:

- `total_theoretical_profit` is a backward-compatible name for summed
  model-implied edge; it is not a result claim.
- `total_realized_profit` remains zero because settlement ingestion is not
  implemented. Direct or mutated live/fill/settlement records raise
  `UnvalidatedLiveExecutionError` until a provenance-bearing validated importer
  exists.
- simulated fills are counted only as simulations.

## Experimental example

```bash
python -m examples.enhanced_system_demo
```

This optional example may require large third-party packages. It is not a
historical backtest, public performance result, or deployment guide.

See [README.md](README.md), [METHODOLOGY.md](METHODOLOGY.md), and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) before using any live public-data path.
