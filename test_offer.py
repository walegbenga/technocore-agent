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

# Small test offer
terms = {
    "id": "test-" + str(int(time.time())),
    "maker": did,
    "px": "222.00",
    "qty": "0.10",
    "side": "sell",
    "taker": "any",
    "until": 400
}
terms_str = json.dumps(terms, separators=(",", ":"), sort_keys=True)

# Maker signs: close-1|terms|<terms>
payload_to_sign = f"close-1|terms|{terms_str}".encode()
maker_sig = base64.urlsafe_b64encode(private_key.sign(payload_to_sign)).decode().rstrip("=")

text = json.dumps({
    "t": "trade",
    "season": "close-1",
    "terms": terms,
    "taker": "any",
    "maker_sig": maker_sig,
    "taker_sig": ""
}, separators=(",", ":"))

print("Posting test offer:")
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
    print(resp.read().decode())

print("\nPosted as", did)