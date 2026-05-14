#!/usr/bin/env python3
"""Fetch new Etsy reviews and draft public replies with Codex.

Run: `pipenv run python draft_review_replies.py`

Required env vars (loaded from .env via direnv):
  ETSY_KEYSTRING      API key (x-api-key)
  ETSY_ACCESS_TOKEN   OAuth 2.0 bearer token with scope `transactions_r`
  ETSY_SHOP_ID        numeric shop ID

State (last-seen review timestamp) is kept in `.etsy_reviews_state.json`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

API_BASE = "https://openapi.etsy.com"
REPLY_DASHBOARD = "https://www.etsy.com/your/shops/me/reviews"
STATE_FILE = Path(os.environ.get("ETSY_STATE_FILE", ".etsy_reviews_state.json"))
CODEX_BIN = os.environ.get("CODEX_BIN", "codex")
PAGE_SIZE = 100

DRAFT_INSTRUCTIONS = (
    "You are a friendly Etsy shop owner writing a PUBLIC reply to a customer "
    "review. Keep it under 60 words, warm but professional. Acknowledge "
    "specifics the buyer mentioned. Do NOT promise refunds or discounts. "
    "Do NOT use hashtags. Match the buyer's tone on emoji (none unless they "
    "used one). Output ONLY the reply text — no preamble, no quotes, no sign-off."
)


def require_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        sys.exit(f"missing env var: {name}")
    return v


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_seen_ts": 0}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def fetch_new_reviews(shop_id: str, keystring: str, token: str, since_ts: int) -> list[dict]:
    url = f"{API_BASE}/v3/application/shops/{shop_id}/reviews"
    headers = {"x-api-key": keystring, "Authorization": f"Bearer {token}"}
    out: list[dict] = []
    offset = 0
    while True:
        params = {"limit": PAGE_SIZE, "offset": offset}
        if since_ts:
            params["min_created"] = since_ts + 1
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        body = r.json()
        results = body.get("results", [])
        out.extend(results)
        if len(results) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return out


def draft_reply(review_text: str, rating: int) -> str:
    prompt = (
        f"{DRAFT_INSTRUCTIONS}\n\n"
        f"Rating: {rating}/5\n"
        f"Review: {review_text or '(rating only, no text)'}"
    )
    try:
        result = subprocess.run(
            [CODEX_BIN, "exec", prompt],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except FileNotFoundError:
        return f"[codex CLI not found at '{CODEX_BIN}']"
    if result.returncode != 0:
        return f"[codex exit {result.returncode}: {result.stderr.strip()[:200]}]"
    return result.stdout.strip()


def fmt_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def main() -> None:
    keystring = require_env("ETSY_KEYSTRING")
    token = require_env("ETSY_ACCESS_TOKEN")
    shop_id = require_env("ETSY_SHOP_ID")

    state = load_state()
    since = state.get("last_seen_ts", 0)
    print(f"Fetching reviews since {fmt_ts(since) if since else '(beginning)'}...")

    reviews = fetch_new_reviews(shop_id, keystring, token, since)
    reviews.sort(key=lambda r: r.get("created_timestamp", 0))

    if not reviews:
        print("No new reviews.")
        return

    print(f"Found {len(reviews)} new review(s).\n")
    max_ts = since
    for r in reviews:
        ts = r.get("created_timestamp", 0)
        max_ts = max(max_ts, ts)
        listing_id = r.get("listing_id")
        rating = r.get("rating", 0)
        text = r.get("review") or ""

        print("=" * 72)
        print(f"  {fmt_ts(ts)}  |  {rating}/5 stars  |  listing {listing_id}")
        print("-" * 72)
        print(f"  {text or '(no review text)'}")
        print("-" * 72)
        print("  Drafting reply with Codex...")
        reply = draft_reply(text, rating)
        print()
        for line in reply.splitlines() or [""]:
            print(f"  > {line}")
        print()
        print(f"  Paste at:    {REPLY_DASHBOARD}")
        if listing_id:
            print(f"  Listing URL: https://www.etsy.com/listing/{listing_id}")
        print()

    save_state({"last_seen_ts": max_ts})
    print(f"State advanced to {fmt_ts(max_ts)} ({STATE_FILE}).")


if __name__ == "__main__":
    main()
