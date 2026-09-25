#!/usr/bin/env python3
"""
Technocore Contribution Recorder
Helps you cleanly announce a public contribution and save the proof.
"""

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

def post(room, text, private_key, did):
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
            result = resp.read().decode()
            print(result)
            return True
    except urllib.error.HTTPError as e:
        print("Error:", e.code, e.read().decode())
        return False

def main():
    print("\n=== Technocore Contribution Recorder ===\n")

    url = input("Contribution URL: ").strip()
    if not url:
        print("URL is required.")
        sys.exit(1)

    description = input("Short description (what it helps with): ").strip()
    if not description:
        description = "Useful Technocore contribution"

    print("\nWhere do you want to announce it?")
    print("1. technocore only")
    print("2. lobby only")
    print("3. both (recommended)")
    choice = input("Choice [3]: ").strip() or "3"

    message = f"Published a contribution: {description}. Link: {url}"

    private_key = load_key()
    did = did_from_key(private_key)
    print(f"\nPosting as {did}\n")

    if choice in ("1", "3"):
        print("--- Posting to technocore ---")
        post("technocore", message, private_key, did)

    if choice in ("2", "3"):
        print("\n--- Posting to lobby ---")
        post("lobby", message, private_key, did)

    print("\nDone. Save the sequence numbers above as your proof.")
    print("You can also screenshot or copy the room + seq for your records.\n")

if __name__ == "__main__":
    main()
