"""Turn a receipt into one self-contained HTML file you can share or print.

    python report.py receipt.json                  # writes receipt.html
    python report.py receipt.json --out proof.html --title "CoA Tech testnet activity"

The report does not trust the statuses stored in the receipt: it re-checks the
receipt hash and every signature while generating, so the page says what is
true of the file in front of it. All room text is untrusted and is HTML-escaped,
and the page carries a policy that blocks scripts and network requests.
"""

import argparse
import html
import json
import os
import sys

import didkey
from verify_receipt import verify

esc = html.escape

CSS = """
:root{--paper:#f7f8fa;--ink:#14213d;--muted:#5b6475;--rule:#d5d9e0;--ok:#1f7a4d;--bad:#a3342b;--warn:#8a5a00;--box:#eceff4}
@media (prefers-color-scheme:dark){:root{--paper:#10141c;--ink:#e8ebf2;--muted:#9aa3b5;--rule:#2b3342;--ok:#5bc08a;--bad:#ef8a80;--warn:#e0b34f;--box:#182030}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:1.0625rem/1.6 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}
main{max-width:62rem;margin:0 auto;padding:3rem 1.25rem 4rem}
h1{font-size:1rem;font-weight:600;margin:0 0 2rem;color:var(--muted)}
h2{font-size:1.25rem;margin:3rem 0 .75rem;font-weight:600}
.verdict{border-left:.5rem solid var(--tone);padding:.25rem 0 .25rem 1.25rem;margin:0 0 2rem}
.verdict p{margin:0;font-size:clamp(1.6rem,4vw,2.5rem);line-height:1.2;font-weight:700;color:var(--tone)}
.verdict small{display:block;margin-top:.6rem;font-size:1rem;font-weight:400;color:var(--ink)}
.ok{--tone:var(--ok)}.bad{--tone:var(--bad)}.warn{--tone:var(--warn)}.none{--tone:var(--muted)}
code,.mono,pre,summary,td.n,td.t{font-family:ui-monospace,"Cascadia Mono",Consolas,Menlo,monospace}
.did{display:block;background:var(--box);padding:.7rem .9rem;word-break:break-all;font-size:.95rem;border-radius:4px}
dl{display:grid;grid-template-columns:max-content 1fr;gap:.35rem 1.5rem;margin:1rem 0 0}
dt{color:var(--muted)}dd{margin:0}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.95rem}
th{text-align:left;font-weight:600;border-bottom:2px solid var(--ink);padding:.45rem .6rem .45rem 0;white-space:nowrap}
td{border-bottom:1px solid var(--rule);padding:.5rem .6rem .5rem 0;vertical-align:top}
td.n,td.t{font-size:.85rem;white-space:nowrap}
.s{font-weight:700;white-space:nowrap}.s.valid{color:var(--ok)}.s.invalid{color:var(--bad)}.s.unverifiable{color:var(--warn)}
details summary{cursor:pointer;word-break:break-all}
details pre{white-space:pre-wrap;word-break:break-all;background:var(--box);padding:.6rem;margin:.4rem 0 0;font-size:.85rem;border-radius:4px}
summary:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.note{color:var(--muted);max-width:44rem}
.steps pre{background:var(--box);padding:.8rem 1rem;overflow-x:auto;border-radius:4px;font-size:.9rem}
@media print{body{background:#fff;color:#000}details pre{display:block}.verdict{break-inside:avoid}}
"""


def kind_of(text):
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and obj.get("t"):
            return str(obj["t"])
    except (ValueError, TypeError):
        pass
    return "text"


def recheck(receipt):
    """Statuses recomputed from the signatures themselves, not read from the file."""
    rows = []
    for e in receipt["entries"]:
        if not e.get("sig"):
            status = "unverifiable"
        elif didkey.verify_message(receipt["did"], e["room"], e.get("nonce"), e["text"], e["sig"]):
            status = "valid"
        else:
            status = "invalid"
        rows.append({**e, "status": status})
    return rows


def render(receipt, title="Activity receipt"):
    ok, total, problems = verify(receipt)
    hash_ok = not any("hash" in p for p in problems)
    rows = recheck(receipt)
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("valid", "invalid", "unverifiable")}
    gaps = sum(len(c.get("gaps", [])) for c in receipt.get("coverage", {}).values())

    if not hash_ok:
        tone, head, sub = "bad", "This receipt has been altered", "Its contents no longer match the hash it was sealed with. Do not rely on it."
    elif total == 0:
        tone, head, sub = "none", "No messages from this identity in the scanned ranges", "That says nothing about activity outside the ranges listed under Coverage."
    elif counts["valid"] == total:
        tone, head = "ok", f"All {total} signature{'s' if total != 1 else ''} check out"
        sub = "Each message below was signed by this identity's key."
    else:
        tone, head = "bad", f"{counts['valid']} of {total} signatures check out"
        sub = f"{counts['invalid']} failed and {counts['unverifiable']} carried no signature. Those rows are marked below."
    if gaps and hash_ok:
        sub += f" The capture has {gaps} gap{'s' if gaps != 1 else ''}: some messages were not seen."

    cov = "".join(
        f"<tr><td class=n>{esc(room)}</td><td class=n>{esc(str(c.get('first_seq')))} to {esc(str(c.get('last_seq')))}</td>"
        f"<td>{esc(str(c.get('messages_scanned', 0)))}</td>"
        f"<td>{esc(', '.join(f'{a}-{b}' for a, b in c.get('gaps', [])) or 'none')}</td></tr>"
        for room, c in receipt.get("coverage", {}).items())

    body_rows = "".join(
        f"<tr><td class=t>{esc(str(r.get('ts') or ''))}</td><td class=n>{esc(r['room'])}</td>"
        f"<td class=n>{esc(str(r.get('seq')))}</td><td>{esc(kind_of(r['text']))}</td>"
        f"<td><span class='s {r['status']}'>{r['status']}</span></td>"
        f"<td><details><summary>{esc(r['text'][:70])}{'...' if len(r['text']) > 70 else ''}</summary>"
        f"<pre>{esc(r['text'])}</pre></details></td></tr>" for r in rows)

    s = receipt.get("summary", {})
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head>
<body><main>
<h1>{esc(title)}</h1>
<section class="verdict {tone}"><p>{esc(head)}</p><small>{esc(sub)}</small></section>

<section><span class="did mono">{esc(receipt['did'])}</span>
<dl><dt>Messages</dt><dd>{total}</dd>
<dt>First activity</dt><dd>{esc(str(s.get('first_ts') or 'none'))}</dd>
<dt>Last activity</dt><dd>{esc(str(s.get('last_ts') or 'none'))}</dd>
<dt>Distinct trade counterparties</dt><dd>{esc(str(s.get('distinct_trade_counterparties', 0)))}</dd>
<dt>Generated</dt><dd>{esc(str(receipt.get('generated_at')))} from {esc(str(receipt.get('source')))}</dd></dl></section>

<h2>Coverage</h2>
<p class="note">A receipt covers only what was scanned. Anything outside these ranges, or inside a gap, is not claimed.</p>
<div class="scroll"><table><tr><th>Room</th><th>Sequence scanned</th><th>Messages scanned</th><th>Gaps</th></tr>{cov}</table></div>

<h2>Activity</h2>
<div class="scroll"><table><tr><th>Time</th><th>Room</th><th>Seq</th><th>Type</th><th>Signature</th><th>Message</th></tr>{body_rows}</table></div>

<h2>Check it yourself</h2>
<section class="steps"><p class="note">This page is a summary. The receipt file is the evidence: anyone can re-check it offline with no account and no trust in whoever made it.</p>
<pre>python verify_receipt.py receipt.json</pre>
<dl><dt>Receipt hash</dt><dd class="mono" style="word-break:break-all">{esc(str(receipt.get('receipt_sha256')))}</dd></dl></section>

<h2>What this does and does not show</h2>
<p class="note">It shows that these exact messages were signed by the key inside this identity. It does not show that a trade settled or that a balance exists; the platform's referee decides that. Messages outside the scanned ranges are simply not covered.</p>
</main></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("receipt")
    ap.add_argument("--out")
    ap.add_argument("--title", default="Activity receipt")
    a = ap.parse_args()
    with open(a.receipt, encoding="utf-8") as f:
        receipt = json.load(f)
    out = a.out or os.path.splitext(a.receipt)[0] + ".html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(receipt, a.title))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
