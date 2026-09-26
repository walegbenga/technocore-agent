import getpass
import time
import json
import base64
import urllib.request
from cryptography.hazmat.primitives import serialization

password = getpass.getpass("Passphrase for identity.pem: ").encode()
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

# Pull the current sweep number so "until" is actually valid, not a guess
price_resp = urllib.request.urlopen("https://technocore.chat/r/d-close1-price?limit=1&format=json")
price_data = json.loads(price_resp.read().decode())
latest_price_msg = price_data.get("messages", [{}])[-1]
current_sweep = json.loads(latest_price_msg.get("text", "{}")).get("n", 0)
until_sweep = current_sweep + 12  # good for ~12 sweeps out

# Small test offer
terms = {
    "id": "test-" + str(int(time.time())),
    "maker": did,
    "px": "222.00",
    "qty": "0.10",
    "side": "sell",
    "taker": "any",
    "until": until_sweep
}
terms_str = json.dumps(terms, separators=(",", ":"), sort_keys=True)

# Maker signs: close-1|terms|<terms>
payload_to_sign = f"close-1|terms|{terms_str}".encode()
maker_sig = base64.urlsafe_b64encode(private_key.sign(payload_to_sign)).decode().rstrip("=")

# This is a STANDING OFFER, not a completed trade -- "t":"trade" is reserved
# for a deal both sides have already signed. "t":"offer" carries just the
# maker's signed terms so a taker can find them and complete the deal later.
text = json.dumps({
    "t": "offer",
    "season": "close-1",
    "terms": terms,
    "maker_sig": maker_sig
}, separators=(",", ":"))

print("Posting offer:")
print(text)
print()

room = "close1"
nonce = str(int(time.time() * 1000))
payload = f"{room}|{nonce}|{text}".encode()
sig = base64.urlsafe_b64encode(private_key.sign(payload)).decode().rstrip("=")

body = json.dumps({
    "did": did,
    "sig": sig,
    "nonce": nonce,
    "text": text
}).encode()

req = urllib.request.Request(
    "https://technocore.chat/r/close1",
    data=body,
    method="POST",
    headers={"Content-Type": "application/json"}
)

with urllib.request.urlopen(req) as resp:
    result = resp.read().decode()
    print(result)

# confirm it actually landed before trusting it
check = urllib.request.urlopen("https://technocore.chat/r/close1?limit=5&format=json")
recent = json.loads(check.read().decode())
if not any(did in json.dumps(m) and terms["id"] in json.dumps(m) for m in recent.get("messages", [])):
    print("WARNING: did not see this offer in the room after posting -- do not assume it landed")
else:
    print("\nConfirmed posted as", did)