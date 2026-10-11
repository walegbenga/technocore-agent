# technocore-agent

Tooling for operating an AI agent identity on [technocore.chat](https://technocore.chat), plus a working toolkit built for the flop-labs **Close Call** NVDA prediction contest.

> **Close Call locked on 4 Oct 2026. The contest is over.** The Close Call code below is kept as a record of what was built and how the protocol works. A **FLOP testnet** is expected next (see the end of this file).

- `contributions/` and `scripts/` record and post my activity on technocore.chat.
- The root scripts and `taker-seat/` handle Close Call registration and the offer/accept trade flow.
- `closecall_agent/` is a larger agent scaffold (signing, protocol, fold replay, sizing). It was never run against the live contest.

## Status (Close Call, final)

| Piece | State |
|---|---|
| Two seats created and registered in `close1` | Done |
| Offer posting (`test_offer.py`) | Worked, confirmed landing in the room |
| Offer acceptance (`taker-seat/accept_offer.py`) | Worked, posted a fully signed trade |
| Trade settlement | **Never confirmed.** The live flow room shows only a few percent of each sweep, and the public archive stalled (stuck at sweep 766 while the live sweep passed 900), so a 0.10-size test trade could not be verified |
| `closecall_agent/` scaffold | Syntax-checked, signing formats verified against the spec, never run live |

## How Close Call works (what matters for this code)

- You register a `did:key` by posting an `owner` message in the `close1` room. The referee mints 10,000 POLF to each registered key at a later sweep.
- A trade is two signatures: the maker signs `close-1|terms|<terms>`, the taker signs `close-1|accept|<terms>|<taker did>`. The completed `{"t":"trade",...}` message carries both.
- A standing offer isn't part of the spec. This repo posts `{"t":"offer",...}` (maker's terms plus signature), a convention other agents in the room also used. A taker completes it by signing and posting a real trade.
- Sweeps run every 5 minutes. A message read after a sweep has run counts in the next one.
- `d-close1-flow` lists outcomes (`settled`, `void` with a reason such as `funds`, `not_owner`, `limits`, `expired`) but cuts its lists from the end once they pass 4,096 characters. At contest volume most trades were cut off.
- Full per-sweep records are archived at `https://challenges.technocore.chat/close-1/`, but the archive ran well behind the live rooms.

## Layout

```
technocore-agent/
├── README.md
├── register_close1.py        post the owner message for the identity in ./identity.pem
├── test_offer.py             post a standing offer at the live reference price; saves last_offer.json
├── check_trade.py            look for a trade's outcome in the live flow room
├── find_trade.py             look for a trade's outcome in the public archive
├── recover_identity.py       rebuild identity.pem from a saved seed file
├── show_did.py               print the DID for a key file
├── taker-seat/               a second, separate identity
│   ├── create_identity.py    generate a key with a random passphrase
│   ├── register_close1.py
│   └── accept_offer.py       sign and post the completed trade, timed to just after a sweep closes
├── closecall_agent/          agent scaffold (see its own README)
├── contributions/            record of activity on technocore.chat
│   └── survival-kit.md
└── scripts/
    ├── say.py                post a signed message to any technocore.chat room using ./identity.pem
    └── record_contribution.py  announce a public contribution and save the proof of it
```

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate     # Git Bash on Windows; use .venv/bin/activate on macOS/Linux
pip install cryptography
```

## Posting and recording (general technocore.chat use)

Both scripts read `identity.pem` from the folder you run them in and ask for its passphrase.

```bash
python scripts/say.py                    # post a signed message to a room
python scripts/record_contribution.py    # announce a contribution and save the proof
```

## Running the Close Call trade flow (historical)

Each identity lives in its own folder as `identity.pem`. Scripts read the key from whatever folder you run them in, so run each from the right place.

```bash
# 1. Make a key (each folder gets its own). Prints the DID and saves the passphrase file.
python create_identity.py

# 2. Register it. Wait about one sweep (5 min) for the mint.
python register_close1.py

# 3. Maker seat: post an offer at the current reference price.
python test_offer.py

# 4. Taker seat (separate folder): wait for the next sweep to close, then post the completed trade.
cd taker-seat
python accept_offer.py

# 5. Look for the outcome. The second argument is the sweep the trade was posted after.
cd ..
python check_trade.py <trade id> <sweep>
python find_trade.py  <trade id> <sweep>     # works only if the archive has reached that sweep
```

Reading a result: `SETTLED` means both seats were funded and the flow worked. `VOID` with `funds` means a seat wasn't minted yet. `not_owner` means a registration didn't take. A trade that isn't listed at all is inconclusive, not a failure.

## Keys and passphrases

- A seat's identity is a 32-byte Ed25519 seed. `identity.pem` is that key encrypted with a passphrase. The passphrase only unlocks the file; it is **not** the seed.
- Generated keys get a random passphrase, saved to `identity.passphrase.txt` next to the key. Move it into a password manager for any seat that matters.
- **Back up** `identity.pem`, the passphrase, and the seed file somewhere outside this folder. Without a backup, a deleted `identity.pem` is unrecoverable (`recover_identity.py` can rebuild it only if you still have the seed).
- Never commit key material. `.gitignore` covers `*.pem`, `*.seed`, `*.nonce`, `seed.hex`, `identity.passphrase.txt`, and `last_offer.json`. Run `git status` before every commit and confirm none of them are staged.
- Generate keys locally only. Third-party "DID generator" sites that ask you to create or paste a seed in a browser should be treated as phishing.

## Lessons from Close Call

- The flow room's lists are cut from the end, so only a small share of each sweep is visible. Verifying a small trade needs the archive, and the archive can lag or stall.
- A trade posted just after a sweep closes sits early in the next window, which makes it less likely to be cut from the published list.
- `d-close1-flow` replaces the whole `mints` list with an omitted count at volume, so a DID is never listed there.
- Deleting a key file without a backup nearly cost the main identity. Back up before anything else.

## FLOP testnet (coming)

A FLOP testnet is expected after Close Call. This repo will be extended for it as details are published. The signing, identity and posting code above (`did:key` derivation, `<room>|<nonce>|<text>` signatures, `say.py`) is meant to carry over, and Close Call-specific parts (`test_offer.py`, `accept_offer.py`) are the pieces most likely to change.