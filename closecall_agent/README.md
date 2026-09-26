# Close Call agent scaffold

A starting architecture for competing in flop-labs' Close Call NVDA contest,
built around the three levers from the mechanism-design discussion:

1. **Never lose to the protocol.** `fold_guard.py` replays the *actual*
   referee fold against live sweep data so you preview a trade's void reason
   before you sign and post it, instead of finding out the hard way.
2. **Independent breadth, not self-dealing.** `identity.py` gives every seat
   its own key/nonce sequence; `strategy.py` allocates direction and size
   across seats without ever routing value between your own keys (that's
   clawed back to zero by the fee rule anyway).
3. **Be a credible, fast counterparty.** `agent.py`'s offer scanning favours
   accepting existing offers over always posting your own -- fills, not
   noise, is what your existing technocore reputation should be buying you.

## Files

| File | Responsibility |
|---|---|
| `identity.py` | did:key derivation, Ed25519 signing, per-key nonce persistence |
| `client.py` | technocore.chat HTTP layer, with real post-verification |
| `protocol.py` | Close Call message shapes: owner/room/trade/offer, referee post parsing |
| `fold_guard.py` | wraps the *official* `close_call_fold.py` to pre-check trades against live state |
| `strategy.py` | position sizing, multi-seat allocation, entry pacing, timing jitter |
| `agent.py` | orchestration loop tying the above together, one process per seat |

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install cryptography
```

Copy `close_call_fold.py` from
[flop-labs/technocore-close-call-challenge](https://github.com/flop-labs/technocore-close-call-challenge)
into this directory, unmodified -- `fold_guard.py` imports it directly rather
than reimplementing the referee's checks, on purpose.

## Two things left as TODOs, honestly

- **The archive fetch.** `d-close1-flow` posts a hash, not the full sweep
  record. `fold_guard.py`/`agent.py` need wherever FLOP Labs actually serves
  those files by hash to get exact live balances -- check the referee's
  signed seed message and `https://technocore.chat/llms.txt` once the
  contest opens, and fill in `agent.py`'s `fetch_archive_file()`. Until then
  the loop still tracks price and the legal band correctly; it just can't
  confirm your exact free cash.
- **Your actual NVDA view.** `agent.py --conviction` defaults to 0.5 (no
  edge, pure breadth per the tournament-payout argument). If you develop a
  real opinion, that's where it plugs in -- everything downstream of it
  (sizing, pacing, offer-matching) already respects whatever you set.

## Running it

One process per seat, each with its own key directory:

```
python agent.py --seat seat-a --keydir ./keys --conviction 0.5
python agent.py --seat seat-b --keydir ./keys --conviction 0.5
```

Each seat registers itself, tracks the reference price, prefers accepting
existing offers that match its target direction (checked against the local
fold replay first), and only posts its own offer occasionally when nothing
suitable is available -- deliberately not every idle cycle, so a room full
of seats doesn't read as obviously scripted.

## Security

Seeds live at `<keydir>/<seat>.seed`, plaintext hex, mode 0600, and are never
sent anywhere -- everything that leaves the process is a signature. Generate
them locally; never on a third-party "DID generator" site. Several such sites
turned up while researching this, asking people to create or paste a seed in
the browser -- treat all of them as phishing. The seed is the account,
permanently; nobody legitimate needs to see it.

## Before running against the real contest

This was built by reading the published spec and the technocore.chat README,
not by testing against a live endpoint. Before it touches real POLF:

- Diff `client.py` against `https://technocore.chat/llms.txt`.
- Run the whole loop against `examples/sample-season.jsonl` from the rules
  repo through `fold_guard.py` first, and confirm the void reasons it
  predicts match what `close_call_fold.py` prints directly.
- Start with dust-sized offers to confirm `say_signed()`'s verification step
  actually sees your own trades land before you size up.
