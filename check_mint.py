import json
import urllib.request

MY_DID = "did:key:z6MkvTnX2DU1q4pBcojVDeLHUouJyGQjD9Tceu5BGMuoz3NR"  # replace with yours

resp = urllib.request.urlopen("https://technocore.chat/r/d-close1-flow?limit=200&format=json")
room = resp.read().decode()

# We don't yet know this room's exact JSON shape for certain -- if this
# doesn't parse as JSON, fall back to a plain text search instead.
found = False
try:
    data = json.loads(room)
    messages = data.get("messages", [])
    for m in messages:
        text = m.get("text", "")
        if MY_DID in text and '"mints"' in text:
            obj = json.loads(text)
            if MY_DID in obj.get("mints", []):
                print(f"Minted at sweep {obj.get('n')}")
                found = True
except json.JSONDecodeError:
    if MY_DID in room:
        print("Found your DID somewhere in the flow room (raw text match) -- inspect manually:")
        print(room)
        found = True

if not found:
    print("No mint found yet for this DID in the recent flow history.")
    print("If you registered less than one sweep ago, just wait for the next sweep and re-run this.")