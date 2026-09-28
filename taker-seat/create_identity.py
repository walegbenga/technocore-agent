import os
import secrets
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

PATH = "identity.pem"
PASS_PATH = "identity.passphrase.txt"

if os.path.exists(PATH):
    print(f"'{PATH}' already exists in this folder -- refusing to overwrite it.")
    print("Delete it first (rm identity.pem) if you want to start over.")
    raise SystemExit(1)

password_str = secrets.token_urlsafe(18)
password = password_str.encode()

private_key = ed25519.Ed25519PrivateKey.generate()

pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.BestAvailableEncryption(password),
)

with open(PATH, "wb") as f:
    f.write(pem)

# Saved next to the key so it can't be lost. Fine for a low-stakes test seat;
# for a seat holding anything you care about, move this into a password
# manager and delete the file.
with open(PASS_PATH, "w") as f:
    f.write(password_str)

for p in (PATH, PASS_PATH):
    try:
        os.chmod(p, 0o600)
    except (AttributeError, NotImplementedError):
        pass

pub = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
multicodec = bytes([0xed, 0x01]) + pub
alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
n = int.from_bytes(multicodec, "big")
res = ""
while n > 0:
    n, r = divmod(n, 58)
    res = alphabet[r] + res
did = "did:key:z" + res

print(f"\nCreated {PATH}")
print(f"DID: {did}")
print(f"\nPassphrase saved to: {PASS_PATH}")
print("Open that file, copy its contents, and paste them when a script asks for the passphrase.")