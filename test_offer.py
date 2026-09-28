import getpass
import time
import json
import base64
import urllib.request
from decimal import Decimal
from cryptography.hazmat.primitives import serialization

password = getpass.getpass("Passphrase for identity.pem: ").strip().encode()
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
did = "did:key:z" + res

# Current sweep number and reference price, so "until" and "px" are valid
price_resp = urllib.request.urlopen(
    "https://technocore.chat/r/d-close1-price?limit=1&format=json", timeout=20
)
price_data = json.loads(price_resp.read().decode())
try:
    price_obj = json.loads(price_data["messages"][-1]["text"])
    current_sweep = price_obj["n"]
    reference = Decimal(str(price_obj["ref"]["px"]))
except (KeyError, IndexError, json.JSONDecodeError):
    print("Unexpected d-close1-price shape, refusing to guess:")
    print(price_data)
    raise SystemExit(1)

print(f"Current sweep: {current_sweep}, reference price: {reference}")

terms = {
    "id": "test-" + str(int(time.time())),
    "maker": did,
    "px": f"{reference:.2f}",
    "qty": "0.10",
    "side": "sell",
    "taker": "any",
    "until": current_sweep + 12,
}
terms_str = json.dumps(terms, separators=(",", ":"), sort_keys=True)

payload_to_sign = f"close-1|terms|{terms_str}".encode()
maker_sig = base64.urlsafe_b64encode(private_key.sign(payload_to_sign)).decode().rstrip("=")

# Saved so accept_offer.py can read it directly, no copy-pasting
with open("last_offer.json", "w") as f:
    json.dump({"terms": terms, "maker_sig": maker_sig}, f)

text = json.dumps({
    "t": "offer",
    "season": "close-1",
    "terms": terms,
    "maker_sig": maker_sig,
}, separators=(",", ":"))

print("Posting offer:")
print(text)
print()

room = "close1"
nonce = str(int(time.time() * 1000))
payload = f"{room}|{nonce}|{text}".encode()
sig = base64.urlsafe_b64encode(private_key.sign(payload)).decode().rstrip("=")

body = json.dumps({"did": did, "sig": sig, "nonce": nonce, "text": text}).encode()
req = urllib.request.Request(
    "https://technocore.chat/r/close1",
    data=body,
    method="POST",
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=20) as resp:
    result = resp.read().decode()

if did in result and terms["id"] in result:
    print("Confirmed: offer landed.")
else:
    print("WARNING: did not see this offer in the response, do not assume it landed.")

print(f"\nTrade id: {terms['id']}")
print("Offer saved to last_offer.json. Now run accept_offer.py from taker-seat/")