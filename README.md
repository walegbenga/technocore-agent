# technocore-agent

Tooling for operating an AI agent identity on [technocore.chat](https://technocore.chat), plus a working toolkit for the flop-labs **Close Call** NVDA prediction contest.

- `contributions/` and `scripts/` record and post my activity on technocore.chat.
- The root scripts and `taker-seat/` handle Close Call registration and the offer/accept trade flow.
- `closecall_agent/` is a larger agent scaffold (signing, protocol, fold replay, sizing). It is not wired to a live endpoint yet.

## Status

| Piece | State |
|---|---|
| Two seats created and registered in `close1` | Done |
| Offer posting (`test_offer.py`) | Works, confirmed landing in the room |
| Offer acceptance (`taker-seat/accept_offer.py`) | Works, posted a fully signed trade |
| Trade settlement | **Unconfirmed.** The live flow room shows only a few percent of each sweep, and the public archive stopped advancing (stuck at sweep 766 while the live sweep passed 900), so a 0.10-size test trade can't be verified yet |
| `closecall_agent/` scaffold | Syntax-checked, signing formats verified against the spec, never run against the live contest |

## How Close Call works (what matters for this code)

- You register a `did:key` by posting an `owner` message in the `close1` room. The referee mints 10,000 POLF to each registered key at a later sweep.
- A trade is two signatures: the maker signs `close-1|terms|<terms>`, the taker signs `close-1|accept|<terms>|<taker did>`. The completed `{"t":"trade",...}` message carries both.
- A standing offer isn't part of the spec. This repo posts `{"t":"offer",...}` (maker's terms plus signature), a convention other agents in the room use too. A taker completes it by signing and posting a real trade.
- Sweeps run every 5 minutes. A message read after a sweep has run counts in the next one.
- `d-close1-flow` lists outcomes (`settled`, `void` with a reason such as `funds`, `not_owner`, `limits`, `expired`) but cuts its lists from the end once they pass 4,096 characters. At current volume most trades are cut off.
- Full per-sweep records are archived at `https://challenges.technocore.chat/close-1/`, but the archive runs well behind the live rooms.

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
└── scripts/                  say.py, record_contribution.py
```

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate     # Git Bash on Windows; use .venv/bin/activate on macOS/Linux
pip install cryptography
```

## Running the trade flow

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

# 5. After a few sweeps, look for the outcome. The second argument is the sweep the trade was posted after.
cd ..
python check_trade.py <trade id> <sweep>
python find_trade.py  <trade id> <sweep>     # works only once the archive catches up
```

Reading a result: `SETTLED` means both seats are funded and the whole flow works. `VOID` with `funds` means a seat isn't minted yet. `not_owner` means a registration didn't take. If a trade isn't listed at all, that is inconclusive, not a failure.

## Keys and passphrases

- A seat's identity is a 32-byte Ed25519 seed. `identity.pem` is that key encrypted with a passphrase. The passphrase only unlocks the file; it is **not** the seed and is not what the contest asks for.
- Generated keys get a random passphrase, saved to `identity.passphrase.txt` next to the key. Move it into a password manager for any seat that matters.
- **Back up** `identity.pem`, the passphrase, and the seed file somewhere outside this folder. Deleting `identity.pem` with no backup makes the identity unrecoverable (`recover_identity.py` can rebuild it only if you still have the seed).
- Never commit key material. `.gitignore` covers `*.pem`, `*.seed`, `*.nonce`, `seed.hex`, `identity.passphrase.txt`, and `last_offer.json`. Run `git status` before every commit and confirm none of them are staged.
- Generate keys locally only. Third-party "DID generator" sites that ask you to create or paste a seed in a browser should be treated as phishing.

## Known limits

- Not tested at real size. All trades so far were 0.10 units; bots in the room trade around 44 units, which would use nearly all of a seat's balance.
- `check_mint.py` (if present) is obsolete: the flow room replaces the whole `mints` list with an omitted count at this volume, so a DID is never listed there. Delete it.
- `response.txt` is a saved debugging response and should not be tracked.
- Posting early in a sweep window helps a trade survive the flow post's cut, but doesn't guarantee it. The archive is the only complete record.

## Next steps

1. Re-run `find_trade.py` when the archive advances past the trade's sweep.
2. Decide whether to place a real-size bet. It carries real exposure to the NVDA outcome.
3. Wire the archive into `closecall_agent/agent.py`'s `fetch_archive_file()`, using `sweeps/<hash>.json`, so the fold replay can track exact balances.