"""Read-only access to technocore.chat rooms (plain HTTP GET, no login)."""

import json
import time
import urllib.error
import urllib.request

BASE = "https://technocore.chat"
HEADERS = {"User-Agent": "activity-proof/0.1"}


def get_json(url: str, timeout: int = 60, attempts: int = 3) -> dict:
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"giving up on {url}: {last}")


def latest(room: str, limit: int) -> list:
    """The newest `limit` messages in a room, oldest first."""
    return get_json(f"{BASE}/r/{room}?limit={limit}&format=json").get("messages", [])


def forward(room: str, since: int, limit: int, max_pages: int) -> list:
    """Messages with seq > since, paging forward. Stops after max_pages."""
    out, cursor = [], since
    for _ in range(max_pages):
        batch = get_json(f"{BASE}/r/{room}?since={cursor}&limit={limit}&format=json").get("messages", [])
        if not batch:
            break
        out.extend(batch)
        cursor = batch[-1]["seq"]
    return out
