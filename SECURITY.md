# Security and execution safety

## Supported security boundary

The default example, tests, and CI require no credentials, wallet, funded
account, private data, or platform network access after dependencies are
installed. Live order submission is not implemented and is hard-disabled.

`BasketExecutor` runs deterministic simulations only. A simulated fill:

- creates no platform order;
- contains no order ID;
- cannot be reported as submitted, filled, settled, or realized performance; and
- remains explicitly marked `simulated` even when the modeled fill status is full.

PredictIt, Kalshi, and historical-backtest paths fail closed.

## Credentials

- Never put a credential or wallet value in source, tests, examples, issues, logs,
  reports, or documentation.
- Store any future local secret in an ignored `.env` or an external secret manager.
- Do not add a credential merely to run the supported path; none is required.
- If a secret is exposed, revoke/rotate it and review access logs. Removing it
  from the current tree does not remove it from Git history.

Report a suspected vulnerability privately to the repository owner. Do not open
a public issue containing a secret value, private account record, or exploit detail.

The redacted scan record for this remediation is in
[SECURITY_REVIEW.md](SECURITY_REVIEW.md).
