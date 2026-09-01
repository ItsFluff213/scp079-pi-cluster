#!/usr/bin/env python3
"""Show or follow the current SCP-079 chat log from relay/Pi 3."""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests


DEFAULT_URL = os.getenv("SCP079_DASHBOARD_URL", "http://logic:7860").rstrip("/")
DEFAULT_TOKEN = os.getenv("SCP079_API_TOKEN", "")


def fetch_messages(url: str, token: str, limit: int, after_id: int) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.get(
        f"{url}/api/chatlog",
        headers=headers,
        params={"limit": limit, "after_id": after_id},
        timeout=(3.0, 20.0),
    )
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
    return response.json()


def print_message(item: dict) -> None:
    ts = item.get("ts", "")
    speaker = item.get("speaker", "unknown")
    source = item.get("source", "?")
    user_text = " ".join(str(item.get("input", "")).split())
    answer = " ".join(str(item.get("answer", "")).split())
    print(f"[{item.get('id')}] {ts} {source} {speaker} > {user_text}")
    print(f"    SCP-079 > {answer}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tail SCP-079 chat log")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--follow", "-f", action="store_true")
    parser.add_argument("--interval", type=float, default=1.2)
    args = parser.parse_args()

    after_id = 0
    while True:
        try:
            payload = fetch_messages(args.url, args.token, args.limit, after_id)
            for item in payload.get("messages", []):
                print_message(item)
                after_id = max(after_id, int(item.get("id", after_id)))
            sys.stdout.flush()
        except Exception as exc:
            print(f"Fehler: {exc}", file=sys.stderr, flush=True)
            if not args.follow:
                raise SystemExit(1) from exc
        if not args.follow:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
