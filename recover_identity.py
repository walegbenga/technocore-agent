import os
import sys
import getpass
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

SEED_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Desktop/seed.hex.save")
EXPECTED_SUFFIX = "Muoz3NR"
OUT = "identity.pem"

if os.path.exists(OUT):
    print(f"'{OUT}' already exists here -- refusing to overwrite it.")
    raise SystemExit(1)

with open(SEED_PATH, "r") as f:
    cleaned = "".join(f.read().split())
if cleaned.lower().startswith("0x"):
    cleaned = cleaned[2:]

try:
    raw = bytes.fromhex(cleaned)
except ValueError:
    print(f"That file is not plain hex (length {len(cleaned)} characters). Stopping.")
    raise SystemExit(1)

if len(raw) == 32:
    seed = raw
elif len(raw) == 64:
    seed = raw[:32]  # some tools store seed + public key together
else:
    print(f"Unexpected size: {len(raw)} bytes (expected 32 or 64). Stopping.")
    raise SystemExit(1)

private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)

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

print("DID from this seed:", did)
if not did.endswith(EXPECTED_SUFFIX):
    print(f"Does NOT end in ...{EXPECTED_SUFFIX}. This is a different key. Nothing was written.")
    raise SystemExit(1)

print("Match. This is your original identity.\n")
pw1 = getpass.getpass("Passphrase for the new identity.pem (your old one works): ").strip()
pw2 = getpass.getpass("Type it again to confirm: ").strip()
if not pw1 or pw1 != pw2:
    print("Passphrases were empty or did not match. Nothing was written.")
    raise SystemExit(1)

pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.BestAvailableEncryption(pw1.encode()),
)

# Prove the file decrypts with that passphrase BEFORE writing it
check = serialization.load_pem_private_key(pem, password=pw1.encode())
assert check.public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw
) == pub

with open(OUT, "wb") as f:
    f.write(pem)
try:
    os.chmod(OUT, 0o600)
except (AttributeError, NotImplementedError):
    pass

print(f"\nRecovered. Wrote {OUT} for {did}")