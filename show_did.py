import getpass
import sys
from cryptography.hazmat.primitives import serialization

path = sys.argv[1] if len(sys.argv) > 1 else "identity.pem"
password = getpass.getpass(f"Passphrase for {path}: ").strip().encode()

with open(path, "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=password)

pub = private_key.public_key().public_bytes_raw()
multicodec = bytes([0xed, 0x01]) + pub
alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
n = int.from_bytes(multicodec, "big")
res = ""
while n > 0:
    n, r = divmod(n, 58)
    res = alphabet[r] + res
print("did:key:z" + res)