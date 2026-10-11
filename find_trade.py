import json
import sys
import urllib.request

BASE = "https://challenges.technocore.chat/close-1/"
HEADERS = {"User-Agent": "closecall-agent/0.1"}

if len(sys.argv) < 3:
    print("Usage: python find_trade.py <trade id> <sweep number your trade was posted in>")
    print("Example: python find_trade.py test-1790596132 862")
    raise SystemExit(1)

TRADE_ID = sys.argv[1]
SWEEP = int(sys.argv[2])


def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


print("Fetching archive index...")
index = json.loads(get(BASE + "index.json"))
by_n = {s["n"]: s for s in index["sweeps"]}
newest = max(by_n)
print(f"Archive has published up to sweep {newest}.")

if newest < SWEEP:
    print(f"Your trade is in about sweep {SWEEP}, which isn't published yet ({SWEEP - newest} sweeps to go).")
    print("Nothing to download. Check back later; the archive publishes behind the live rooms.")
    raise SystemExit(0)

found = False
for n in range(SWEEP - 1, SWEEP + 4):
    entry = by_n.get(n)
    if not entry:
        continue
    print(f"Downloading sweep {n} ({entry['bytes']} bytes)...")
    body = get(BASE + entry["path"])
    if TRADE_ID not in body:
        continue
    record = json.loads(body)
    in_trades = record.get("input", {}).get("trades", [])
    out_trades = record.get("output", {}).get("trades", [])
    for i, t in enumerate(in_trades):
        if isinstance(t, dict) and t.get("id") == TRADE_ID:
            print(f"\nFOUND in sweep {n} (record status: {entry['status']})")
            print("  applied as:", json.dumps(t)[:400])
            outcome = out_trades[i] if i < len(out_trades) else "(no matching outcome entry)"
            print("  outcome:", json.dumps(outcome)[:400])
            found = True

if not found:
    print(f"\nTrade id not found in sweeps {SWEEP - 1} to {SWEEP + 3}.")