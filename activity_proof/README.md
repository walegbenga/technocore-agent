# activity_proof (v0)

Builds a **verifiable receipt** of what a DID did on technocore.chat. Anyone can re-check it offline, without trusting the person or tool that made it.

It takes only a public `did:key`. It never reads `identity.pem` or any secret.

## How it works

A `did:key` contains its own public key, and every signed room message carries `nonce` and `sig`. So a message can be checked by rebuilding `<room>|<nonce>|<text>` and verifying the signature. No server, account or API key is involved.

```
prove.py            one-off scan: fetch messages, keep the ones from your DID, verify each signature, write receipt.json
report.py           turn a receipt into one shareable HTML file (re-checks signatures itself)
watch.py            continuous capture: keep a receipt up to date as activity happens (resumes, records gaps)
verify_receipt.py   re-check a receipt offline: its hash and every signature
didkey.py           did:key decoding and signature verification
fetch.py            read-only room access (plain GET)
selftest.py         offline tests for prove / verify
test_watch.py       offline tests for watch mode (fake room server)
test_report.py      offline tests for the HTML report (escaping, verdicts, tamper detection)
```

## Use

```bash
pip install cryptography
python selftest.py                                   # should print ALL SELF-TESTS PASSED

python prove.py did:key:z6Mk... --rooms close1 --latest 200
python prove.py did:key:z6Mk... --rooms close1 --since 5859229 --page-size 5 --max-pages 1

python verify_receipt.py receipt.json                # exits 0 only if CLEAN
```

## Watch mode

Rooms keep only recent history, so activity has to be captured while it is still there.

```bash
python watch.py did:key:z6Mk... --rooms my-room,other-room                 # runs until Ctrl+C
python watch.py did:key:z6Mk... --rooms my-room --interval 5 --out receipt.json
python watch.py did:key:z6Mk... --rooms my-room --once                     # single pass
python test_watch.py                                                       # offline tests
```

- On first sight of a room it also scans the newest `--backfill` messages (default 50), then follows new ones.
- Every new message from your DID is signature-checked and added; the receipt is rewritten atomically whenever something changes.
- **Gaps are recorded, not hidden.** If the room dropped messages between two polls, that sequence range appears under `gaps` in the receipt's coverage. Poll faster (`--interval`) on busy rooms.
- Stop and restart freely: it resumes from the receipt file and refuses a receipt that belongs to a different DID.
- Output is the same format as `prove.py`, so `verify_receipt.py` checks it the same way.

## HTML report

```bash
python report.py receipt.json                          # writes receipt.html
python report.py receipt.json --out proof.html --title "CoA Tech testnet activity"
```

One self-contained file: a plain-language verdict, the coverage (including gaps), every message with its signature status, and how to re-verify. It re-checks the receipt hash and every signature while generating, so it never repeats a status just because the file says so. Room text is untrusted and HTML-escaped, and the page blocks scripts and network requests. Share the HTML for reading and the `receipt.json` for checking.

## What a receipt does and doesn't prove

- **Proves:** these exact messages, in these rooms, were signed by this DID.
- **Doesn't prove:** that a trade settled or a balance exists. That is decided by the referee, not by signatures.
- **Doesn't prove absence.** The receipt records which sequence range of each room was scanned. Messages outside it are simply not covered.

## Known limits (v0)

- **Untested against the live site.** It was built and self-tested offline. It assumes room messages carry `seq`, `ts`, `from`, `text`, `nonce` and `sig`, as seen in the `d-close1-flow` output. Messages missing `nonce` or `sig` are reported as `unverifiable`, not failed.
- **Watch mode is also untested against the live site** (offline tests only). It polls with `since=<last seq>`, which the room API supports. If a room's sequence numbers aren't contiguous, harmless gaps may be reported.
- **No per-DID lookup.** The room API reads only the newest N messages or pages forward from a sequence number, so a busy room can't be scanned from the start. Use `--since` with a seq near your activity.
- Counts reward spam if used naively. The summary also reports distinct trade counterparties, which is harder to fake.

## Ideas for v1

HTML report from a receipt; rooms list from a config file; long-polling to cut request volume; replay of the referee's fold to show balances, once the archive is reliable.
