"""Offline tests for the HTML report: escaping, verdicts, tamper detection."""

import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import didkey
from prove import build_receipt
from report import render


def key():
    p = Ed25519PrivateKey.generate()
    return p, didkey.did_from_pubkey(p.public_key().public_bytes_raw())


def msg(p, did, room, seq, text):
    n = 1000 + seq
    sig = base64.urlsafe_b64encode(p.sign(f"{room}|{n}|{text}".encode())).decode().rstrip("=")
    return {"seq": seq, "ts": f"2026-10-14T10:00:{seq:02d}Z", "from": did, "nonce": n, "text": text, "sig": sig}


me_p, me = key()
ot_p, _ = key()
R = "demo"
attack = '<script>alert(1)</script><img src=x onerror=alert(2)>'
good = [msg(me_p, me, R, 1, attack), msg(me_p, me, R, 2, '{"t":"owner","season":"close-1"}')]
scan = {"mode": "latest", "requested": 10}

r = build_receipt(me, {R: {"messages": good, "scan": scan}})
page = render(r, "Test")
assert "<script>" not in page and "<img" not in page and "&lt;script&gt;" in page
assert "All 2 signatures check out" in page
print("1. hostile message text is escaped, clean receipt shows the green verdict: OK")

forged = good + [msg(ot_p, me, R, 3, "forged")]
page = render(build_receipt(me, {R: {"messages": forged, "scan": scan}}))
assert "2 of 3 signatures check out" in page and "invalid" in page
print("2. a forged message is called out: OK")

t = json.loads(json.dumps(r))
t["entries"][0]["text"] = "edited"
assert "This receipt has been altered" in render(t)
print("3. an edited receipt is reported as altered: OK")

# a validly sealed receipt whose stored statuses lie must still be caught
from prove import assemble
base = build_receipt(me, {R: {"messages": forged, "scan": scan}})
lying_entries = [{**e, "status": "valid"} for e in base["entries"]]
liar = assemble(me, lying_entries, base["coverage"])
page = render(liar)
assert "This receipt has been altered" not in page and "2 of 3 signatures check out" in page
print("4. stored statuses are ignored, signatures are re-checked: OK")

empty = build_receipt(me, {R: {"messages": [], "scan": scan}})
assert "No messages from this identity" in render(empty)
print("5. empty receipt says so plainly: OK")
print("\nALL REPORT TESTS PASSED")
