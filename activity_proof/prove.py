"""Build a verifiable activity receipt for a DID.

    python prove.py did:key:z6Mk... --rooms close1,d-close1-flow --latest 200
    python prove.py did:key:z6Mk... --rooms close1 --since 5859000 --max-pages 20

Takes only a PUBLIC did:key. It never reads identity.pem or any secret.
Every message from that DID is signature-checked locally; the receipt records
exactly which sequence range of each room was scanned, because a receipt can
prove what it contains but never what was outside the scanned range.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone

import didkey
import fetch


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def receipt_hash(body: dict) -> str:
    return hashlib.sha256(canonical(body).encode()).hexdigest()


def classify(did: str, room: str, m: dict) -> str:
    if "sig" not in m or "nonce" not in m or not m.get("sig"):
        return "unverifiable"
    return "valid" if didkey.verify_message(did, room, m["nonce"], m.get("text", ""), m["sig"]) else "invalid"


def summarize(did: str, entries: list) -> dict:
    types, counterparties = Counter(), set()
    for e in entries:
        try:
            obj = json.loads(e["text"])
        except (ValueError, TypeError):
            types["(not json)"] += 1
            continue
        if not isinstance(obj, dict):
            types["(not an object)"] += 1
            continue
        types[str(obj.get("t", "(no type)"))] += 1
        if obj.get("t") == "trade":
            terms = obj.get("terms") or {}
            for other in (terms.get("maker"), obj.get("taker")):
                if other and other != did and other != "any":
                    counterparties.add(other)
    stamps = sorted(e["ts"] for e in entries if e.get("ts"))
    return {
        "messages": len(entries),
        "by_status": dict(Counter(e["status"] for e in entries)),
        "by_room": dict(Counter(e["room"] for e in entries)),
        "by_type": dict(types),
        "distinct_trade_counterparties": len(counterparties),
        "first_ts": stamps[0] if stamps else None,
        "last_ts": stamps[-1] if stamps else None,
    }


def build_receipt(did: str, scanned: dict) -> dict:
    """`scanned` maps room -> {"messages": [...], "scan": {...}}. Pure function, no network."""
    entries, coverage = [], {}
    for room, data in scanned.items():
        msgs = data["messages"]
        seqs = [m["seq"] for m in msgs if "seq" in m]
        coverage[room] = {**data["scan"], "messages_scanned": len(msgs),
                          "first_seq": min(seqs) if seqs else None,
                          "last_seq": max(seqs) if seqs else None}
        for m in msgs:
            if m.get("from") != did:
                continue
            entries.append({"room": room, "seq": m.get("seq"), "ts": m.get("ts"),
                            "nonce": m.get("nonce"), "text": m.get("text", ""),
                            "sig": m.get("sig"), "status": classify(did, room, m)})
    return assemble(did, entries, coverage)


def assemble(did: str, entries: list, coverage: dict) -> dict:
    """Sort entries, add the summary and timestamp, and seal the receipt with its hash.
    Shared by prove.py (one-off scans) and watch.py (continuous capture)."""
    entries = sorted(entries, key=lambda e: (e["ts"] or "", e["room"], e["seq"] or 0))
    body = {"version": 1, "did": did, "source": fetch.BASE,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "coverage": coverage, "summary": summarize(did, entries), "entries": entries}
    return {**body, "receipt_sha256": receipt_hash(body)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("did")
    ap.add_argument("--rooms", default="close1", help="comma-separated room names")
    ap.add_argument("--latest", type=int, default=200, help="newest N messages per room")
    ap.add_argument("--since", type=int, help="instead, scan forward from this seq")
    ap.add_argument("--max-pages", type=int, default=10)
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--out", default="receipt.json")
    a = ap.parse_args()

    try:
        didkey.pubkey_from_did(a.did)
    except ValueError as e:
        sys.exit(f"Bad DID: {e}")

    scanned = {}
    for room in [r.strip() for r in a.rooms.split(",") if r.strip()]:
        print(f"Scanning {room} ...", flush=True)
        if a.since is None:
            msgs, scan = fetch.latest(room, a.latest), {"mode": "latest", "requested": a.latest}
        else:
            msgs = fetch.forward(room, a.since, a.page_size, a.max_pages)
            scan = {"mode": "forward", "since": a.since, "max_pages": a.max_pages}
        scanned[room] = {"messages": msgs, "scan": scan}

    receipt = build_receipt(a.did, scanned)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)

    s = receipt["summary"]
    print(f"\nDID: {a.did}\nMessages from this DID in the scanned ranges: {s['messages']}")
    print(f"Signature status: {s['by_status']}\nBy room: {s['by_room']}\nBy type: {s['by_type']}")
    print(f"Distinct trade counterparties: {s['distinct_trade_counterparties']}")
    for room, c in receipt["coverage"].items():
        print(f"  scanned {room}: {c['messages_scanned']} messages, seq {c['first_seq']} to {c['last_seq']}")
    print(f"\nReceipt written to {a.out}\nsha256: {receipt['receipt_sha256']}")
    if s["by_status"].get("invalid"):
        print("WARNING: some messages failed signature verification. Inspect them in the receipt.")


if __name__ == "__main__":
    main()
