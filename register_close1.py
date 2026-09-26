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

# confirm it actually landed before trusting it -- a 200 only means the
# server accepted the HTTP request, not that the signature verified
check = urllib.request.urlopen("https://technocore.chat/r/close1?limit=5&format=json")
recent = json.loads(check.read().decode())
if not any(did in json.dumps(m) for m in recent.get("messages", [])):
    print("WARNING: did not see this DID in the room after posting -- do not assume it registered")
else:
    print("\nConfirmed registered as", did)