import getpass
import json
import os
import time
import base64
import urllib.request
from cryptography.hazmat.primitives import serialization

OFFER_FILE = "../last_offer.json"
if os.path.exists(OFFER_FILE):
    with open(OFFER_FILE) as f:
        offer = json.load(f)
else:
    offer = json.loads(input("Paste the offer JSON from test_offer.py: ").strip())

terms = offer["terms"]
maker_sig = offer["maker_sig"]

password = getpass.getpass("Passphrase for THIS identity.pem: ").strip().encode()
with open("identity.pem", "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=password)

pub = private_key.public_key().public_bytes_raw()
multicodec = bytes([0xed, 0x01]) + pub
alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
n = int.from_bytes(multicodec, "big")
res = ""
while n > 0:
    n, r = divmod(n, 58)
    res = alphabet[r] + res
taker_did = "did:key:z" + res

if taker_did == terms["maker"]:
    print("This is the same identity that made the offer. Run this from taker-seat/.")
    raise SystemExit(1)

# Refuse to post an offer that has already expired
price_resp = urllib.request.urlopen(
    "https://technocore.chat/r/d-close1-price?limit=1&format=json", timeout=20
)
price_data = json.loads(price_resp.read().decode())
current_sweep = json.loads(price_data["messages"][-1]["text"])["n"]
if terms["until"] <= current_sweep:
    print(f"Offer expired (good through sweep {terms['until']}, now sweep {current_sweep}).")
    print("Run test_offer.py again for a fresh one.")
    raise SystemExit(1)

terms_str = json.dumps(terms, separators=(",", ":"), sort_keys=True)

# Taker signs: close-1|accept|<terms>|<taker did:key>
accept_payload = f"close-1|accept|{terms_str}|{taker_did}".encode()
taker_sig = base64.urlsafe_b64encode(private_key.sign(accept_payload)).decode().rstrip("=")

text = json.dumps({
    "t": "trade",
    "season": "close-1",
    "terms": terms,
    "taker": taker_did,
    "maker_sig": maker_sig,
    "taker_sig": taker_sig,
}, separators=(",", ":"))

print("Posting completed trade:")
print(text)

room = "close1"
nonce = str(int(time.time() * 1000))
payload = f"{room}|{nonce}|{text}".encode()
sig = base64.urlsafe_b64encode(private_key.sign(payload)).decode().rstrip("=")

body = json.dumps({"did": taker_did, "sig": sig, "nonce": nonce, "text": text}).encode()
req = urllib.request.Request(
    "https://technocore.chat/r/close1",
    data=body,
    method="POST",
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=20) as resp:
    result = resp.read().decode()

if taker_did in result and terms["id"] in result:
    print("\nConfirmed posted. Check the next sweep with check_trade.py")
else:
    print("\nWARNING: did not see this in the response, do not assume it landed.")

print(f"Trade id: {terms['id']}")