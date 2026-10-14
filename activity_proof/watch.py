"""Watch mode: keep a verifiable receipt up to date while you work.

    python watch.py did:key:z6Mk... --rooms my-room,other-room
    python watch.py did:key:z6Mk... --rooms my-room --interval 5 --out receipt.json
    python watch.py did:key:z6Mk... --rooms my-room --once          # one pass, then exit

Rooms only keep recent history, so activity has to be captured while it is still
there. This polls each room, signature-checks every new message from your DID,
and rewrites the receipt (same format as prove.py) whenever something changes.

Honest coverage: if the room dropped messages between two polls, that missing
sequence range is recorded under "gaps" in the receipt. A receipt can then say
"I captured everything from seq A to B except these ranges" instead of implying
completeness. Stop and restart freely: it resumes from the receipt file.
Takes only a public DID; never reads identity.pem.
"""

import argparse
import json
import os
import sys
import time

import didkey
import fetch
import prove


class Watcher:
    def __init__(self, did, rooms, path="receipt.json", fetcher=fetch,
                 page_size=100, max_pages=20, backfill=50, log=print):
        self.did, self.rooms, self.path, self.f = did, rooms, path, fetcher
        self.page_size, self.max_pages, self.backfill = page_size, max_pages, max(1, backfill)
        self.log = log
        self.entries = {}      # (room, seq) -> entry
        self.coverage = {}     # room -> coverage record
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as fh:
            r = json.load(fh)
        if r.get("did") != self.did:
            raise SystemExit(f"{self.path} belongs to a different DID. Use --out for a new file.")
        for e in r.get("entries", []):
            self.entries[(e["room"], e["seq"])] = e
        self.coverage = r.get("coverage", {})
        self.log(f"Resuming from {self.path}: {len(self.entries)} entries, rooms {list(self.coverage)}")

    def _cov(self, room):
        c = self.coverage.setdefault(room, {})
        c.setdefault("mode", "watch")
        c.setdefault("first_seq", None)
        c.setdefault("last_seq", 0)
        c.setdefault("messages_scanned", 0)
        c.setdefault("gaps", [])
        return c

    def _poll_room(self, room):
        """Fetch new messages for one room. Returns (new_entries, backlog_hit)."""
        cov = self._cov(room)
        initial = cov["first_seq"] is None
        if initial:
            msgs = self.f.latest(room, self.backfill)
        else:
            msgs = self.f.forward(room, cov["last_seq"], self.page_size, self.max_pages)
        backlog = (not initial) and len(msgs) >= self.page_size * self.max_pages

        added, prev = 0, (None if initial else cov["last_seq"])
        for m in msgs:
            seq = m.get("seq")
            if seq is None or (not initial and seq <= cov["last_seq"]):
                continue
            if prev is not None and seq > prev + 1:
                cov["gaps"].append([prev + 1, seq - 1])
                self.log(f"  gap in {room}: seq {prev + 1} to {seq - 1} not captured")
            prev = seq
            cov["messages_scanned"] += 1
            if cov["first_seq"] is None:
                cov["first_seq"] = seq
            cov["last_seq"] = max(cov["last_seq"], seq)
            if m.get("from") == self.did and (room, seq) not in self.entries:
                status = prove.classify(self.did, room, m)
                self.entries[(room, seq)] = {
                    "room": room, "seq": seq, "ts": m.get("ts"), "nonce": m.get("nonce"),
                    "text": m.get("text", ""), "sig": m.get("sig"), "status": status}
                added += 1
                self.log(f"  captured {room} seq {seq}: {status}")
        return added, backlog

    def step(self):
        """One pass over every room. Saves the receipt if anything changed."""
        total_new, backlog = 0, False
        before = json.dumps(self.coverage, sort_keys=True)
        for room in self.rooms:
            added, hit = self._poll_room(room)
            total_new += added
            backlog = backlog or hit
        if total_new or json.dumps(self.coverage, sort_keys=True) != before:
            self.save()
        return total_new, backlog

    def save(self):
        receipt = prove.assemble(self.did, list(self.entries.values()), self.coverage)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(receipt, fh, indent=2)
        os.replace(tmp, self.path)   # atomic: a crash never leaves a half-written receipt
        return receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("did")
    ap.add_argument("--rooms", required=True, help="comma-separated room names")
    ap.add_argument("--out", default="receipt.json")
    ap.add_argument("--interval", type=float, default=10, help="seconds between polls")
    ap.add_argument("--backfill", type=int, default=50, help="on first sight of a room, also scan its newest N messages")
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--max-pages", type=int, default=20)
    ap.add_argument("--once", action="store_true", help="poll once and exit")
    a = ap.parse_args()

    try:
        didkey.pubkey_from_did(a.did)
    except ValueError as e:
        sys.exit(f"Bad DID: {e}")

    rooms = [r.strip() for r in a.rooms.split(",") if r.strip()]
    w = Watcher(a.did, rooms, a.out, page_size=a.page_size, max_pages=a.max_pages, backfill=a.backfill)
    print(f"Watching {rooms} for {a.did[:20]}... every {a.interval}s. Ctrl+C to stop.")
    try:
        while True:
            try:
                _, backlog = w.step()
            except RuntimeError as e:          # network trouble: report and keep going
                print(f"  poll failed ({e}); will retry")
                backlog = False
            if a.once:
                break
            time.sleep(0 if backlog else a.interval)
    except KeyboardInterrupt:
        print("\nStopping.")
    r = w.save()
    s = r["summary"]
    print(f"Receipt {a.out}: {s['messages']} messages, status {s['by_status']}")
    print(f"sha256: {r['receipt_sha256']}")


if __name__ == "__main__":
    main()
