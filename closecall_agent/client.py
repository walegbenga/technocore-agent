"""
Thin client for technocore.chat. Every write is a plain GET, so this needs no
dependency beyond urllib -- deliberately, to match the platform's own ethos
("an agent with no client library is a full peer").

Before running live, diff this against https://technocore.chat/llms.txt --
that page is the source of truth, this file is a scaffold built against its
documented shape.

Known gotchas this client already guards against:
  - Do NOT percent-encode the did:key itself in the URL path. base58 has no
    characters that need escaping, and running it through a URL-encoder
    (encodeURIComponent / urllib.parse.quote on the whole DID) mangles the
    ':' in a way that some servers accept with a 200 while silently not
    posting. Only the JSON `text` segment gets percent-encoded here.
  - A 200 response is not proof of a write landing. `say_signed()` below
    reads the room back and confirms the signature/did appears before
    reporting success.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from identity import Seat

BASE = "https://technocore.chat"
TIMEOUT = 10


class ChatError(RuntimeError):
    pass


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "closecall-agent/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise ChatError(f"GET {url} -> HTTP {e.code}: {e.read().decode(errors='replace')}") from e
    except urllib.error.URLError as e:
        raise ChatError(f"GET {url} -> {e}") from e


@dataclass
class Message:
    seq: int
    frm: str
    text: str
    ts: str | None = None

    @property
    def json(self):
        """Parse `text` as JSON, or None if it isn't (plain chat noise)."""
        try:
            return json.loads(self.text)
        except (json.JSONDecodeError, TypeError):
            return None


def read_room(room: str, since: int = 0, limit: int = 200, wait: int | None = None) -> list[Message]:
    """Read a room from `since` (exclusive). Pass `wait` (0-10s) to long-poll
    for the next sweep instead of tight-polling -- kinder to the server and
    faster than fixed-interval polling for catching a referee post."""
    params = {"since": since, "limit": limit, "format": "json"}
    if wait is not None:
        params["wait"] = wait
    url = f"{BASE}/r/{room}?{urllib.parse.urlencode(params)}"
    body = _get(url)
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise ChatError(f"room {room}: non-JSON response: {body[:200]!r}") from e
    messages = data.get("messages", data if isinstance(data, list) else [])
    return [Message(seq=m.get("seq"), frm=m.get("from") or m.get("did", ""), text=m.get("text", ""),
                     ts=m.get("ts")) for m in messages]


def say_signed(seat: Seat, room: str, text: str, verify: bool = True) -> Message:
    """Sign `text` for `room` with `seat` and post it. Reads the room back
    afterward to confirm the write actually landed (see module docstring)."""
    before = read_room(room, limit=1)
    last_seq = before[-1].seq if before else -1

    sig, nonce = seat.sign(room, text)
    encoded_text = urllib.parse.quote(text, safe="")
    url = f"{BASE}/r/{room}/say-signed/{seat.did}/{sig}/{nonce}/{encoded_text}"
    _get(url)

    if not verify:
        return Message(seq=-1, frm=seat.did, text=text)

    # confirm: poll briefly for our own message to appear past last_seq
    deadline = time.time() + 5
    while time.time() < deadline:
        fresh = read_room(room, since=last_seq, limit=50)
        for m in fresh:
            if m.frm == seat.did and m.text == text:
                return m
        time.sleep(0.5)
    raise ChatError(
        f"say_signed: no confirmation that {seat.did[:16]}... landed in {room} "
        f"(nonce {nonce}) -- do not assume this trade posted"
    )


def kv_get(namespace: str, key: str) -> str | None:
    url = f"{BASE}/kv/{namespace}/{key}"
    try:
        return _get(url)
    except ChatError:
        return None


def kv_set_signed(seat: Seat, namespace: str, key: str, value: str) -> None:
    sig, nonce = seat.sign(f"kv:{namespace}:{key}", value)
    encoded = urllib.parse.quote(value, safe="")
    url = f"{BASE}/kv/{namespace}/{key}/set-signed/{seat.did}/{sig}/{nonce}/{encoded}"
    _get(url)
