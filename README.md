# etsy

Experiments against the [Etsy Open API v3](https://developers.etsy.com/documentation/).

## Setup

Requires `pipenv`, `direnv`, and the `codex` CLI on `PATH`.

```bash
cp .env.example .env          # fill in credentials
pipenv install
direnv allow
```

`.envrc` activates the pipenv virtualenv and sources `.env` whenever you `cd` into this directory.

### Environment

| Var | Purpose |
| --- | --- |
| `ETSY_KEYSTRING` | API key — sent as `x-api-key` |
| `ETSY_SHARED_SECRET` | OAuth client secret |
| `ETSY_ACCESS_TOKEN` | OAuth 2.0 bearer token (scope `transactions_r` for reviews) |
| `ETSY_SHOP_ID` | Numeric shop ID |
| `ETSY_RATE_LIMIT_QPS` / `ETSY_RATE_LIMIT_QPD` | Local throttling hints |

## Scripts

### `draft_review_replies.py`

Pulls reviews newer than the last run, drafts a public reply with `codex exec`, and prints the dashboard URL where you paste it. State is tracked in `.etsy_reviews_state.json`.

```bash
pipenv run python draft_review_replies.py
```

The Etsy API has no endpoint for posting review replies, so the final paste step is manual by design.
