"""
Identity: one did:key per agent seat.

Each seat is a 32-byte Ed25519 seed on disk, never transmitted anywhere.
technocore.chat and the Close Call referee both use the same scheme:
  did      = "did:key:z" + base58btc(0xed 0x01 + raw_pubkey)
  sig      = base64url_nopad(Ed25519_sign(f"{room}|{nonce}|{text}"))

SECURITY: generate seeds locally, in this process, on a machine you control.
Several "DID generator" websites circulate in the technocore community asking
people to paste or create a seed in the browser -- treat every one of them as
a phishing attempt. The seed IS the account; nobody legitimate needs to see it.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_MULTICODEC_ED25519_PUB = bytes([0xED, 0x01])  # varint prefix for an Ed25519 public key


def _b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n > 0:
        n, rem = divmod(n, 58)
        out = _B58_ALPHABET[rem] + out
    n_leading_zero_bytes = len(data) - len(data.lstrip(b"\x00"))
    return "1" * n_leading_zero_bytes + out


def _b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@dataclass
class Seat:
    """One trading identity: a keypair, its did:key, and its own nonce counter."""

    name: str
    seed_path: Path
    nonce_path: Path
    private_key: Ed25519PrivateKey
    did: str

    def sign(self, room: str, text: str) -> tuple[str, int]:
        """Sign `<room>|<nonce>|<text>` and return (signature, nonce_used).

        `text` must already be the exact compact JSON you intend to post --
        sign what you send, byte for byte. The nonce is consumed and persisted
        before the network call, so a crash never reuses a nonce.
        """
        nonce = self._next_nonce()
        payload = f"{room}|{nonce}|{text}".encode("utf-8")
        sig = self.private_key.sign(payload)
        return _b64url_nopad(sig), nonce

    def sign_raw(self, payload: str) -> str:
        """Sign an exact string with no nonce and no room framing. Used for
        Close Call's own terms/accept signatures, which are embedded inside
        the JSON payload rather than being technocore.chat post signatures."""
        return _b64url_nopad(self.private_key.sign(payload.encode("utf-8")))

    def _next_nonce(self) -> int:
        current = 0
        if self.nonce_path.exists():
            current = int(self.nonce_path.read_text().strip() or 0)
        nxt = current + 1
        # write-then-return: if this crashes mid-write, resync() below recovers
        self.nonce_path.write_text(str(nxt))
        return nxt

    def resync_nonce_from(self, last_seen_nonce: int) -> None:
        """Call this if a room read shows a higher nonce than our local file
        (e.g. after restoring a seat on a new machine, or a lost write)."""
        current = int(self.nonce_path.read_text().strip() or 0) if self.nonce_path.exists() else 0
        if last_seen_nonce > current:
            self.nonce_path.write_text(str(last_seen_nonce))


def load_or_create_seat(name: str, keydir: str | Path) -> Seat:
    """Load a seat's key from `<keydir>/<name>.seed`, or create one.

    One seat = one independent trading key. For multi-key breadth (see
    strategy.py), just call this with different `name`s -- each gets its own
    seed file, its own did:key, and its own nonce sequence, so the seats never
    collide on-protocol and never need to know about each other.
    """
    keydir = Path(keydir)
    keydir.mkdir(parents=True, exist_ok=True)
    seed_path = keydir / f"{name}.seed"
    nonce_path = keydir / f"{name}.nonce"

    if seed_path.exists():
        seed = bytes.fromhex(seed_path.read_text().strip())
        priv = Ed25519PrivateKey.from_private_bytes(seed)
    else:
        seed = os.urandom(32)
        priv = Ed25519PrivateKey.from_private_bytes(seed)
        # 0600: this file is the entire account, forever
        fd = os.open(seed_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(seed.hex())

    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    did = "did:key:z" + _b58encode(_MULTICODEC_ED25519_PUB + pub_bytes)

    return Seat(name=name, seed_path=seed_path, nonce_path=nonce_path, private_key=priv, did=did)


def list_seats(keydir: str | Path) -> list[str]:
    keydir = Path(keydir)
    if not keydir.exists():
        return []
    return sorted(p.stem for p in keydir.glob("*.seed"))
