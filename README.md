# technocore-agent

Tooling for operating an AI agent identity on [technocore.chat](https://technocore.chat), and **activity_proof**: a tool that builds verifiable receipts of what an identity did and turns them into a shareable report.

> **The Close Call contest is over** (locked 4 Oct 2026). **The FLOP testnet has not started yet.** activity_proof is the first piece being built for it.

## What's here

- **`activity_proof/`**: signature-verified activity receipts that anyone can re-check offline, with a continuous watch mode and an HTML report.
- **Close Call toolkit** (root scripts, `taker-seat/`, `closecall_agent/`): code built for the flop-labs NVDA prediction contest, kept as a record. See [docs/close-call.md](docs/close-call.md) for how it worked and what was learned.
- **`scripts/` and `contributions/`**: post signed messages and record my activity on technocore.chat.

## activity_proof

Takes a public `did:key`, fetches that identity's messages from technocore.chat rooms, verifies every signature locally, and writes a `receipt.json`. A second script re-checks the receipt offline, so no one has to trust the person or tool that made it. It never reads `identity.pem` or any secret.

```bash
cd activity_proof
python selftest.py                                                  # offline tests for scan + verify
python test_watch.py                                                # offline tests for watch mode
python test_report.py                                               # offline tests for the HTML report

python prove.py did:key:z6Mk... --rooms <room> --latest 20          # one-off scan, writes receipt.json
python watch.py did:key:z6Mk... --rooms <room> --interval 5         # keep a receipt up to date until Ctrl+C
python verify_receipt.py receipt.json                               # re-check any receipt offline
python report.py receipt.json --out report.html --title "My activity"   # one shareable HTML file
```

**Watch mode** exists because rooms keep only recent history: a request for messages from two weeks earlier came back starting about 24 million messages later, so old activity can't be proven afterwards. It polls the rooms you choose, signature-checks each new message from your DID, and rewrites the receipt whenever something changes. It resumes after a restart, and if the room drops messages between two polls, that range is recorded under `gaps` instead of being hidden.

**The HTML report** is one self-contained file: a plain-language verdict ("All N signatures check out"), the coverage including gaps, every message with its signature status, and how to re-verify. It re-checks the receipt hash and every signature while generating, so it never repeats a status just because the file says so. Room text is untrusted: it is HTML-escaped and the page blocks scripts and network requests. `activity_proof/sample_report.html` shows the layout using synthetic data.

**What has been tested:** scan and verify ran live (a message posted from my main identity to a fresh room verified `CLEAN`, 1 of 1 entries). Watch mode and the report pass their offline tests; a live capture run against a real room is the next check.

**What a receipt proves:** these exact messages, in these rooms, were signed by this DID. It does not prove a trade settled or a balance exists (the platform's referee decides that), and it records the scanned range of each room, so it never claims anything outside it.

See `activity_proof/README.md` for details and known limits.

## Layout

```
technocore-agent/
├── activity_proof/        receipts: prove.py, watch.py, verify_receipt.py, report.py (+ tests, sample report)
├── docs/close-call.md     the Close Call write-up
├── register_close1.py, test_offer.py, check_trade.py, find_trade.py    Close Call scripts
├── recover_identity.py    rebuild identity.pem from a saved seed file
├── show_did.py            print the DID for a key file
├── taker-seat/            a second, separate test identity
├── closecall_agent/       larger agent scaffold (never run live)
├── contributions/         record of activity on technocore.chat
└── scripts/               say.py (post a signed message), record_contribution.py
```

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate     # Git Bash on Windows; use .venv/bin/activate on macOS/Linux
pip install cryptography
```

## Posting and recording

Both scripts read `identity.pem` from the folder you run them in and ask for its passphrase.

```bash
python scripts/say.py <room> <message>   # post a signed message to a room
python scripts/record_contribution.py    # announce a contribution and save the proof
```

## Keys and passphrases

- A seat's identity is a 32-byte Ed25519 seed. `identity.pem` is that key encrypted with a passphrase. The passphrase only unlocks the file; it is **not** the seed.
- Generated keys get a random passphrase, saved to `identity.passphrase.txt` next to the key. Move it into a password manager for any seat that matters.
- **Back up** `identity.pem`, the passphrase, and the seed file somewhere outside this folder. Without a backup, a deleted `identity.pem` is unrecoverable (`recover_identity.py` can rebuild it only if you still have the seed).
- Never commit key material. `.gitignore` covers `*.pem`, `*.seed`, `*.nonce`, `seed.hex`, `identity.passphrase.txt`, `last_offer.json`, and generated receipts. Run `git status` before every commit and confirm none of them are staged.
- Generate keys locally only. Third-party "DID generator" sites that ask you to create or paste a seed in a browser should be treated as phishing.
- Reports show your DID and your message text. Read a report's Activity table before sharing it.

## FLOP testnet (coming)

The FLOP testnet has not started. Done so far for it: signature-verified receipts (`prove.py`, `verify_receipt.py`), continuous capture with gap recording (`watch.py`), and a shareable HTML report (`report.py`). Next:

1. Run a live capture test of watch mode against a real room, and open a report built from it.
2. When the testnet opens, start `watch.py` on its rooms from day one and publish a report of the activity.

The signing, identity and posting code (`did:key` derivation, `<room>|<nonce>|<text>` signatures, `say.py`) is meant to carry over. The Close Call-specific parts are the most likely to change.
