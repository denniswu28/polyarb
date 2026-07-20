# Third-party review notes

Reviewed 2026-07-19. This is an engineering inventory, not a legal conclusion.
License names below are the expressions reported by the linked project metadata;
the applicable license is the one shipped with the exact artifact that is installed.

## Declared direct dependencies

| Scope | Package | Reported license metadata | Source |
|---|---|---|---|
| Core | Requests | Apache-2.0 | [PyPI](https://pypi.org/project/requests/) |
| Core | python-dotenv | BSD-3-Clause | [PyPI](https://pypi.org/project/python-dotenv/) |
| Core | SQLAlchemy | MIT | [PyPI](https://pypi.org/project/SQLAlchemy/) |
| Core | HTTPX | BSD-3-Clause | [PyPI](https://pypi.org/project/httpx/) |
| `embeddings` extra | Chroma | Apache-2.0 | [PyPI](https://pypi.org/project/chromadb/) |
| `embeddings` extra | NumPy | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | [PyPI](https://pypi.org/project/numpy/) |
| `embeddings` extra | scikit-learn | BSD-3-Clause | [PyPI](https://pypi.org/project/scikit-learn/) |
| `embeddings` extra | sentence-transformers | Apache-2.0 | [PyPI](https://pypi.org/project/sentence-transformers/) |
| `postgres` extra | psycopg2-binary | LGPL with exceptions | [PyPI](https://pypi.org/project/psycopg2-binary/) |
| Development | pytest | MIT | [PyPI](https://pypi.org/project/pytest/) |
| Development | pytest-asyncio | Apache-2.0 | [PyPI](https://pypi.org/project/pytest-asyncio/) |
| Development | pytest-cov | MIT | [PyPI](https://pypi.org/project/pytest-cov/) |
| Development | Ruff | MIT | [PyPI](https://pypi.org/project/ruff/) |

The import surface was compared with `pyproject.toml`: the four packages needed
by ordinary imports are core dependencies. The unauthenticated read-only CLOB
path uses core HTTPX; embedding/model and PostgreSQL drivers remain extras.
`requirements.txt` mirrors the core set and
`requirements-dev.txt` installs the package's `dev` extra.

The former `py-clob-client` extra and dynamic adapter were removed after review:
the referenced [client is archived](https://github.com/Polymarket/py-clob-client)
and the integration did not initialize its published client class. The
repository has not adopted or tested the separate
[V2 client](https://github.com/Polymarket/py-clob-client-v2). This is an
engineering status statement, not a conclusion about either project's terms or
fitness.

## API and platform terms to review

- [Polymarket terms](https://polymarket.com/tos) and
  [developer documentation](https://docs.polymarket.com/)
- [PredictIt terms](https://www.predictit.org/terms-and-conditions)
- [Kalshi developer agreement](https://kalshi.com/developer-agreement),
  [API documentation](https://docs.kalshi.com/welcome), and
  [rulebook](https://kalshi.com/regulatory/rulebook)

These links are references, not a statement that a use is permitted. Anyone who
opts into public API access must review current access, geography, data-use,
rate-limit, market, and trading rules. PredictIt and Kalshi are not implemented;
live order submission is disabled.

## Attribution and unresolved items

- The repository is MIT-licensed; provenance is recorded in `PROVENANCE.md`.
- A current-tree text review found no separate source or copyright notice in the
  examples. That does not establish origin or clearance; the owner must confirm
  that examples and documentation need no additional attribution.
- There is no lock file, so future installations may resolve different versions
  and transitive dependencies. Review the license files in the exact resolved
  artifacts before distribution.
- Optional sentence-transformer model weights and any user-supplied data have
  their own terms and are outside this inventory.
- Transitive dependencies, binary-component notices, platform-rule changes, and
  redistribution obligations remain unresolved owner/legal-review items.
