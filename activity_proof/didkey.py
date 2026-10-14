"""did:key helpers: recover the public key from a DID and verify signatures.

A did:key for Ed25519 is "did:key:z" + base58btc(0xed 0x01 + 32-byte public key),
so the DID itself carries everything needed to check a signature. No secrets here.
"""

import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
PREFIX = b"\xed\x01"


def b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n > 0:
        n, r = divmod(n, 58)
        out = ALPHABET[r] + out
    return "1" * (len(data) - len(data.lstrip(b"\x00"))) + out


def b58decode(text: str) -> bytes:
    n = 0
    for ch in text:
        idx = ALPHABET.find(ch)
        if idx < 0:
            raise ValueError(f"invalid base58 character {ch!r}")
        n = n * 58 + idx
    zeros = len(text) - len(text.lstrip("1"))
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * zeros + body


def did_from_pubkey(pub: bytes) -> str:
    return "did:key:z" + b58encode(PREFIX + pub)


def pubkey_from_did(did: str) -> bytes:
    if not did.startswith("did:key:z"):
        raise ValueError("not a did:key (expected did:key:z...)")
    raw = b58decode(did[len("did:key:z"):])
    if len(raw) != 34 or raw[:2] != PREFIX:
        raise ValueError("not an Ed25519 did:key")
    return raw[2:]


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def verify_message(did: str, room: str, nonce, text: str, sig: str) -> bool:
    """True only if `sig` is a valid signature by `did` over "<room>|<nonce>|<text>"."""
    try:
        key = Ed25519PublicKey.from_public_bytes(pubkey_from_did(did))
        key.verify(b64url_decode(sig), f"{room}|{nonce}|{text}".encode("utf-8"))
        return True
    except (InvalidSignature, ValueError):
        return False
