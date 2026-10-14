"""Offline tests for watch mode, using a fake room server. No network."""

import base64
import json
import os
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import didkey
from verify_receipt import verify
from watch import Watcher


def make_key():
    priv = Ed25519PrivateKey.generate()
    return priv, didkey.did_from_pubkey(priv.public_key().public_bytes_raw())


def signed(priv, did, room, seq, text, nonce=None):
    nonce = nonce or 1000 + seq
    sig = base64.urlsafe_b64encode(priv.sign(f"{room}|{nonce}|{text}".encode())).decode().rstrip("=")
    return {"seq": seq, "ts": f"2026-10-14T10:00:{seq:02d}Z", "from": did, "nonce": nonce, "text": text, "sig": sig}


class FakeRoomServer:
    def __init__(self):
        self.rooms = {}

    def add(self, room, msg):
        self.rooms.setdefault(room, []).append(msg)

    def latest(self, room, limit):
        return self.rooms.get(room, [])[-limit:]

    def forward(self, room, since, limit, max_pages):
        return [m for m in self.rooms.get(room, []) if m["seq"] > since][: limit * max_pages]


me_priv, me = make_key()
other_priv, other = make_key()
srv = FakeRoomServer()
R = "test-room"
quiet = lambda *a, **k: None

tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "receipt.json")

# 1. First sight: backfill finds my earlier message
for seq in range(1, 6):
    who, wp = (me, me_priv) if seq == 2 else (other, other_priv)
    srv.add(R, signed(wp, who, R, seq, f"msg {seq}"))
w = Watcher(me, [R], path, fetcher=srv, log=quiet)
new, _ = w.step()
assert new == 1 and w.coverage[R]["first_seq"] == 1 and w.coverage[R]["last_seq"] == 5, w.coverage
print("1. backfill captures earlier message: OK")

# 2. New messages arrive, one is mine; nothing duplicated on an idle poll
for seq in range(6, 10):
    who, wp = (me, me_priv) if seq == 7 else (other, other_priv)
    srv.add(R, signed(wp, who, R, seq, f"msg {seq}"))
assert w.step()[0] == 1
assert w.step()[0] == 0
assert len(w.entries) == 2 and w.coverage[R]["last_seq"] == 9 and w.coverage[R]["gaps"] == []
print("2. live capture, no duplicates on idle poll: OK")

# 3. The room drops seq 11-13 between polls: must be recorded as a gap
srv.add(R, signed(other_priv, other, R, 10, "msg 10"))
srv.add(R, signed(me_priv, me, R, 14, "mine after the gap"))
assert w.step()[0] == 1
assert w.coverage[R]["gaps"] == [[11, 13]], w.coverage[R]["gaps"]
print("3. dropped messages recorded as a gap: OK")

# 4. A message claiming to be me but signed by someone else is kept and flagged
forged = signed(other_priv, me, R, 15, "forged")
srv.add(R, forged)
w.step()
assert w.entries[(R, 15)]["status"] == "invalid"
print("4. forged message flagged invalid: OK")

# 5. Restart: resumes from the file, no duplicate entries, no false gap
count_before = len(w.entries)
w2 = Watcher(me, [R], path, fetcher=srv, log=quiet)
assert len(w2.entries) == count_before
srv.add(R, signed(me_priv, me, R, 16, "after restart"))
assert w2.step()[0] == 1 and len(w2.entries) == count_before + 1
assert w2.coverage[R]["gaps"] == [[11, 13]]
print("5. restart resumes cleanly: OK")

# 6. A receipt file for a different DID is refused
try:
    Watcher(other, [R], path, fetcher=srv, log=quiet)
    raise AssertionError("should have refused")
except SystemExit:
    pass
print("6. refuses another DID's receipt file: OK")

# 7. The saved receipt is sealed correctly: only the forged entry is a problem
r = json.load(open(path))
ok, total, problems = verify(r)
assert not any("hash" in p for p in problems), problems
assert total == len(r["entries"]) and len(problems) == 1 and "seq 15" in problems[0], problems
assert not os.path.exists(path + ".tmp")
print("7. receipt hash intact, forged entry reported, no temp file left: OK")

# 8. A second room is tracked independently
srv.add("room-b", signed(me_priv, me, "room-b", 1, "hello b"))
w3 = Watcher(me, [R, "room-b"], path, fetcher=srv, log=quiet)
assert w3.step()[0] == 1 and w3.coverage["room-b"]["last_seq"] == 1
print("8. multiple rooms: OK")

print("\nALL WATCH TESTS PASSED")
