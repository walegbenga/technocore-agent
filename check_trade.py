import json
import urllib.request
import sys

TRADE_ID = sys.argv[1] if len(sys.argv) > 1 else input("Trade id to check: ").strip()

resp = urllib.request.urlopen(
    "https://technocore.chat/r/d-close1-flow?limit=50&format=json", timeout=20
)
room = json.loads(resp.read().decode())

found = False
for m in room.get("messages", []):
    try:
        obj = json.loads(m["text"])
    except (KeyError, json.JSONDecodeError):
        continue
    if TRADE_ID in obj.get("settled", []):
        print(f"SETTLED at sweep {obj['n']}")
        found = True
    for vid, reason in obj.get("void", []):
        if vid == TRADE_ID:
            print(f"VOID at sweep {obj['n']}, reason: {reason}")
            found = True

if not found:
    print("Not seen yet in the last 50 sweep records -- may not have run yet, or is older than this window.")