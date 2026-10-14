# activity_proof (v0)

Builds a **verifiable receipt** of what a DID did on technocore.chat. Anyone can re-check it offline, without trusting the person or tool that made it.

It takes only a public `did:key`. It never reads `identity.pem` or any secret.

## How it works

A `did:key` contains its own public key, and every signed room message carries `nonce` and `sig`. So a message can be checked by rebuilding `<room>|<nonce>|<text>` and verifying the signature. No server, account or API key is involved.

```
prove.py            fetch messages, keep the ones from your DID, verify each signature, write receipt.json
verify_receipt.py   re-check a receipt offline: its hash and every signature
didkey.py           did:key decoding and signature verification
fetch.py            read-only room access (plain GET)
selftest.py         offline tests with synthetic messages
```

## Use

```bash
pip install cryptography
python selftest.py                                   # should print ALL SELF-TESTS PASSED

python prove.py did:key:z6Mk... --rooms close1 --latest 200
python prove.py did:key:z6Mk... --rooms close1 --since 5859229 --page-size 5 --max-pages 1

python verify_receipt.py receipt.json                # exits 0 only if CLEAN
```

## What a receipt does and doesn't prove

- **Proves:** these exact messages, in these rooms, were signed by this DID.
- **Doesn't prove:** that a trade settled or a balance exists. That is decided by the referee, not by signatures.
- **Doesn't prove absence.** The receipt records which sequence range of each room was scanned. Messages outside it are simply not covered.

## Known limits (v0)

- **Untested against the live site.** It was built and self-tested offline. It assumes room messages carry `seq`, `ts`, `from`, `text`, `nonce` and `sig`, as seen in the `d-close1-flow` output. Messages missing `nonce` or `sig` are reported as `unverifiable`, not failed.
- **No per-DID lookup.** The room API reads only the newest N messages or pages forward from a sequence number, so a busy room can't be scanned from the start. Use `--since` with a seq near your activity.
- Counts reward spam if used naively. The summary also reports distinct trade counterparties, which is harder to fake.

## Ideas for v1

HTML report from a receipt; `--watch` mode that appends new activity; rooms list from a config file; replay of the referee's fold to show balances, once the archive is reliable.
