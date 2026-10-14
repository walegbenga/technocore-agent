"""Offline self-test with synthetic messages. No network, no real keys."""

import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import didkey
from prove import build_receipt
from verify_receipt import verify


def sign(priv, room, nonce, text):
    sig = priv.sign(f"{room}|{nonce}|{text}".encode())
    return base64.urlsafe_b64encode(sig).decode().rstrip("=")


def make_key():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes_raw()
    return priv, didkey.did_from_pubkey(pub)


me_priv, me = make_key()
other_priv, other = make_key()

# DID round trip, and the shape the contest regex expects
assert didkey.pubkey_from_did(me) == me_priv.public_key().public_bytes_raw()
assert me.startswith("did:key:z6Mk") and len(me) == 56, me

owner = json.dumps({"t": "owner", "season": "close-1", "key": me}, separators=(",", ":"))
trade = json.dumps({"t": "trade", "season": "close-1", "taker": me,
                    "terms": {"maker": other, "id": "x1"}}, separators=(",", ":"))
msgs = [
    {"seq": 1, "ts": "2026-10-01T10:00:00Z", "from": me, "nonce": 1000, "text": owner, "sig": sign(me_priv, "close1", 1000, owner)},
    {"seq": 2, "ts": "2026-10-01T10:00:01Z", "from": other, "nonce": 5, "text": "hello", "sig": sign(other_priv, "close1", 5, "hello")},
    {"seq": 3, "ts": "2026-10-01T10:05:00Z", "from": me, "nonce": 1001, "text": trade, "sig": sign(me_priv, "close1", 1001, trade)},
    # forged: claims to be me but signed by someone else
    {"seq": 4, "ts": "2026-10-01T10:06:00Z", "from": me, "nonce": 1002, "text": "forged", "sig": sign(other_priv, "close1", 1002, "forged")},
    # no signature fields at all
    {"seq": 5, "ts": "2026-10-01T10:07:00Z", "from": me, "text": "plain post"},
]
receipt = build_receipt(me, {"close1": {"messages": msgs, "scan": {"mode": "latest", "requested": 200}}})
s = receipt["summary"]
assert s["messages"] == 4, s                       # other's message excluded
assert s["by_status"] == {"valid": 2, "invalid": 1, "unverifiable": 1}, s["by_status"]
assert s["distinct_trade_counterparties"] == 1, s
assert receipt["coverage"]["close1"]["first_seq"] == 1 and receipt["coverage"]["close1"]["last_seq"] == 5
print("build_receipt: OK")

# Verifier flags the forged entry and the unsigned one, and accepts the rest
ok, total, problems = verify(receipt)
assert (ok, total) == (2, 4) and len(problems) == 2, (ok, total, problems)
print("verify_receipt flags forged + unsigned entries: OK")

# Editing the receipt after the fact breaks its hash
tampered = json.loads(json.dumps(receipt))
tampered["entries"][0]["text"] = "edited"
_, _, problems = verify(tampered)
assert any("hash" in p for p in problems), problems
print("tampering detected: OK")

# Clean receipt (only genuine messages) verifies fully
clean = build_receipt(me, {"close1": {"messages": msgs[:1] + msgs[2:3], "scan": {"mode": "latest", "requested": 2}}})
ok, total, problems = verify(clean)
assert (ok, total, problems) == (2, 2, []), problems
print("clean receipt verifies: OK")
print("\nALL SELF-TESTS PASSED")
