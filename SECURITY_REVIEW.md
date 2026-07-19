# Redacted secret-scan review

Scan date: 2026-07-19. Tool: `detect-secrets` 1.5.0 with its default detectors,
offline verification disabled. Candidate values are intentionally omitted.

| Scope | Coverage | Findings | Paths and categories | Remediation |
|---|---|---:|---|---|
| Current working tree | All relevant files; Git metadata, environments, caches, and build output excluded | 0 | None | No action required from this scan |
| Reachable Git history through the review-fix commit | 52 reachable commits; 203 unique blobs | 3 | `ENHANCED_SYSTEM.md` — Basic Auth Credentials (1); `examples/add_custom_platform.py` — Secret Keyword (1); `polyarb/data/database.py` — Basic Auth Credentials (1) | Example/template strings were removed or rewritten in the current tree; history was not rewritten |

The historical results are detector candidates in documentation or example
contexts, not evidence that a working credential was committed. Dennis reports
that no credentials, wallet material, private trades, or account records were
committed. This automated scan does not prove absence; GitHub-side secret
scanning and an independent review should remain enabled where available.

If an independent reviewer determines that a historical candidate is real,
revoke it first, assess access logs, and then decide whether a coordinated
history rewrite is warranted. Do not paste candidate values into an issue or PR.
