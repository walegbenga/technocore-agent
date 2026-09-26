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

text = json.dumps({
    "t": "owner",
    "season": "close-1",
    "key": did
}, separators=(",", ":"))

print("Posting:", text)

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

# the response body above already contains the room tail -- just check
# your own DID shows up as the newest entry in it
if did in result:
    print("\nConfirmed: your DID appears in the response above -- registration landed.")
else:
    print("\nWARNING: did not see this DID in the response -- do not assume it registered.")