# Quick start: deterministic offline scan

Supported Python versions are 3.10, 3.11, and 3.12, as exercised in CI.

From a fresh clone on Windows or Linux:

```bash
python -m pip install .
python -m examples.demo_with_mock_data
```

The example uses committed synthetic data. It does not require a network,
credential, wallet, funded account, or private record, and it cannot submit an
order. Its output is a list of model-implied research candidates under printed
fee and slippage assumptions—not trades or performance.

## Development checks

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m examples.demo_with_mock_data
```

## Opt-in network examples

These commands contact Polymarket public endpoints and are intentionally excluded
from tests and CI:

```bash
python -m examples.basic_usage
python -m examples.single_event_multi_market_scan --limit 200 --min-profit 0.5
```

They do not enable live order submission. Review current platform access and data
terms before running them. PredictIt and Kalshi adapters are not implemented and
raise `NotImplementedError`.

## Optional experimental modules

```bash
python -m pip install -e ".[embeddings,postgres]"
python -m examples.enhanced_system_demo
```

The enhanced demo is experimental and is not the supported reproducibility path.
Historical backtesting, dashboards, and live execution are not implemented.

See [README.md](README.md) for the evidence matrix and lifecycle definitions.
