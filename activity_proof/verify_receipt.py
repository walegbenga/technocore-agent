"""Re-check a receipt offline. Needs no network and no trust in whoever made it.

    python verify_receipt.py receipt.json

Checks (1) the receipt's own hash and (2) every entry's signature against the
public key inside the DID. Exits 0 only if everything is clean.
"""

import json
import sys

import didkey
from prove import receipt_hash


def verify(receipt: dict) -> tuple:
    problems = []
    body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    if receipt_hash(body) != receipt.get("receipt_sha256"):
        problems.append("receipt hash does not match its contents (file was edited)")
    did, ok = receipt["did"], 0
    for e in receipt["entries"]:
        good = bool(e.get("sig")) and didkey.verify_message(did, e["room"], e.get("nonce"), e["text"], e["sig"])
        if good:
            ok += 1
        else:
            problems.append(f"{e['room']} seq {e.get('seq')}: signature does not verify")
    return ok, len(receipt["entries"]), problems


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python verify_receipt.py receipt.json")
    with open(sys.argv[1], encoding="utf-8") as f:
        r = json.load(f)
    ok, total, problems = verify(r)
    print(f"DID: {r['did']}\nVerified {ok} of {total} entries.")
    for p in problems:
        print(" -", p)
    print("RESULT:", "CLEAN" if not problems else "PROBLEMS FOUND")
    sys.exit(0 if not problems else 1)
