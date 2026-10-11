import json
import sys
import urllib.request

if len(sys.argv) < 3:
    print("Usage: python check_trade.py <trade id> <sweep it was posted after>")
    print("Example: python check_trade.py test-1790597656 869")
    raise SystemExit(1)

TRADE_ID = sys.argv[1]
SWEEP = int(sys.argv[2])
URL = "https://technocore.chat/r/d-close1-flow"


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())


# Work out how the room's sequence numbers line up with sweep numbers
latest = get(f"{URL}?limit=1&format=json")
newest_n = json.loads(latest["messages"][-1]["text"])["n"]
offset = latest["last_seq"] - newest_n
print(f"Live sweep is {newest_n}. Reading sweeps {SWEEP} to {SWEEP + 2}.\n")

room = get(f"{URL}?since={SWEEP - 2 + offset}&limit=6&format=json")
posts = {}
for m in room.get("messages", []):
    try:
        obj = json.loads(m["text"])
        posts[obj["n"]] = obj
    except (KeyError, json.JSONDecodeError):
        pass

hit = False
for n in range(SWEEP, SWEEP + 3):
    p = posts.get(n)
    if p is None:
        print(f"Sweep {n}: post not in the room's history window.")
        continue
    settled = p.get("settled", [])
    void = p.get("void", [])
    om = p.get("omitted", {})
    print(f"Sweep {n}: showing {len(settled)} settled and {len(void)} void; "
          f"cut off: {om.get('settled', 0)} settled, {om.get('void', 0)} void")
    if TRADE_ID in settled:
        print(f"  >>> SETTLED in sweep {n}")
        hit = True
    for vid, reason in void:
        if vid == TRADE_ID:
            print(f"  >>> VOID in sweep {n}, reason: {reason}")
            hit = True

if not hit:
    print("\nNot listed in these sweeps. That means one of two things:")
    print("  - the referee applied it and the post's list was cut before reaching it, or")
    print("  - it was never read. The lists show only a small share of what happened.")
    print("Neither is proof either way.")