# Data policy

## Included

- Deterministic synthetic/mock records committed for examples and tests.
- Source code that can optionally request public Polymarket endpoints when a user
  deliberately runs a network example.

## Excluded

- Credentials, tokens, private keys, seed phrases, or wallet material.
- Private account identifiers, holdings, orders, fills, settlements, or trade records.
- Employer-derived code, data, parameters, documents, or proprietary methods.
- Redistributed vendor/platform datasets or historical order books.
- Public performance or profit records.

Generated databases, reports, account exports, and local `.env` files must remain
untracked. Before adding any dataset, document its source, license/terms,
collection date, schema, permitted redistribution, and sanitization method.

Live public API output is not a committed dataset and is outside the supported
offline reproduction path. API availability does not imply permission to store,
redistribute, or use the data for trading.
