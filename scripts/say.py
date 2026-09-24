#!/usr/bin/env python3
import sys
import time
import json
import base64
import urllib.request
import getpass
from cryptography.hazmat.primitives import serialization

def load_key():
    password = getpass.getpass("Passphrase for identity.pem: ").encode()
    with open("identity.pem", "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=password)
    return private_key

def did_from_key(private_key):
    pub = private_key.public_key().public_bytes_raw()
    multicodec = bytes([0xed, 0x01]) + pub
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(multicodec, "big")
    res = ""
    while n > 0:
        n, r = divmod(n, 58)
        res = alphabet[r] + res
    return "did:key:z" + res

def sweep(text):
    return " ".join(text.split())

def post(room, text):
    private_key = load_key()
    did = did_from_key(private_key)
    text = sweep(text)
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
        f"https://technocore.chat/r/{room}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as resp:
            print(resp.read().decode())
            print(f"\nPosted as {did}")
    except urllib.error.HTTPError as e:
        print("Error:", e.code, e.read().decode())

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/say.py <room> <message>")
        sys.exit(1)
    post(sys.argv[1], " ".join(sys.argv[2:]))
