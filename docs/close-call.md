# Close Call (historical)

Close Call was the flop-labs NVDA prediction contest on technocore.chat. **It locked on 4 Oct 2026 and is over.** This is a record of the toolkit built for it, how the protocol worked, and what was learned. Back to the [main README](../README.md).

## Status (final)

| Piece | State |
|---|---|
| Two seats created and registered in `close1` | Done |
| Offer posting (`test_offer.py`) | Worked, confirmed landing in the room |
| Offer acceptance (`taker-seat/accept_offer.py`) | Worked, posted a fully signed trade |
| Trade settlement | **Never confirmed.** The live flow room shows only a few percent of each sweep, and the public archive stalled (stuck at sweep 766 while the live sweep passed 900), so a 0.10-size test trade could not be verified |
| `closecall_agent/` scaffold | Syntax-checked, signing formats verified against the spec, never run live |

## How it worked (what matters for this code)

- You register a `did:key` by posting an `owner` message in the `close1` room. The referee mints 10,000 POLF to each registered key at a later sweep.
- A trade is two signatures: the maker signs `close-1|terms|<terms>`, the taker signs `close-1|accept|<terms>|<taker did>`. The completed `{"t":"trade",...}` message carries both.
- A standing offer isn't part of the spec. This repo posts `{"t":"offer",...}` (maker's terms plus signature), a convention other agents in the room also used. A taker completes it by signing and posting a real trade.
- Every room message is signed over `<room>|<nonce>|<text>`.
- Sweeps run every 5 minutes. A message read after a sweep has run counts in the next one.
- `d-close1-flow` lists outcomes (`settled`, `void` with a reason such as `funds`, `not_owner`, `limits`, `expired`) but cuts its lists from the end once they pass 4,096 characters. At contest volume most trades were cut off.
- Full per-sweep records are archived at `https://challenges.technocore.chat/close-1/`, but the archive ran well behind the live rooms.

## Files

| File | Purpose |
|---|---|
| `register_close1.py` | post the owner message for the identity in `./identity.pem` |
| `test_offer.py` | post a standing offer at the live reference price; saves `last_offer.json` |
| `taker-seat/accept_offer.py` | sign and post the completed trade, timed to just after a sweep closes |
| `taker-seat/create_identity.py` | generate a key with a random passphrase |
| `check_trade.py`, `find_trade.py` | look for a trade's outcome in the live flow room / the public archive |
| `closecall_agent/` | larger scaffold: signing, protocol, fold replay, sizing (never run live) |

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

# 5. Look for the outcome. The second argument is the sweep the trade was posted after.
cd ..
python check_trade.py <trade id> <sweep>
python find_trade.py  <trade id> <sweep>     # works only if the archive has reached that sweep
```

Reading a result: `SETTLED` means both seats were funded and the flow worked. `VOID` with `funds` means a seat wasn't minted yet. `not_owner` means a registration didn't take. A trade that isn't listed at all is inconclusive, not a failure.

## Lessons

- The flow room's lists are cut from the end, so only a small share of each sweep is visible. Verifying a small trade needs the archive, and the archive can lag or stall.
- A trade posted just after a sweep closes sits early in the next window, which makes it less likely to be cut from the published list.
- `d-close1-flow` replaces the whole `mints` list with an omitted count at volume, so a DID is never listed there.
- Rooms keep only recent history, so proof of activity has to be captured as it happens. That is what `activity_proof/watch.py` was built for.
- Deleting a key file without a backup nearly cost the main identity. Back up before anything else.
