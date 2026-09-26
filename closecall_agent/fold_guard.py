"""
Don't reimplement the referee's checker -- replay the REAL one.

Copy `close_call_fold.py` from flop-labs/technocore-close-call-challenge into
this directory unmodified (it's the pinned, hash-verified source of truth;
see contest.json / the seed message for which commit is live). This module
feeds it the live sweep records so your local `Fold` object always mirrors
the referee's actual ledger, then lets you preview a candidate trade's void
reason before you ever sign and post it.

One real gap, stated plainly rather than hidden: the `funds` check depends on
that sweep's fee, and the fee depends on `close` -- Hyperliquid's real trade
at the sweep boundary -- which nobody knows until after the sweep runs. So
`would_settle()` below checks everything else exactly, and estimates the fee
using the trade's own price as a stand-in for `close` (i.e. assumes no
clawback). That's a lower-bound fee estimate, so it can pass a trade that
then goes `funds`-void if the real close moves against you between now and
settlement -- leave headroom in your sizing (see strategy.py) rather than
spending a key down to the cent.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Callable

try:
    from close_call_fold import Fold, amount  # the vendored, unmodified official fold
except ImportError as e:
    raise ImportError(
        "close_call_fold.py not found next to this file. Copy it verbatim from "
        "flop-labs/technocore-close-call-challenge -- see this module's docstring."
    ) from e


class LiveFold:
    def __init__(self, config: dict | None = None):
        self.fold = Fold(config)
        self.last_reference: Decimal | None = None

    # -- feeding it real referee output --------------------------------

    def apply_seed(self, price_obj: dict) -> None:
        self.fold.seed(price_obj["px"])

    def apply_sweep_record(self, record: dict) -> dict:
        """`record` is the full per-sweep file the flow room's `file` hash
        points at: {"n":..,"ref":..,"close":..,"owners":[...],"trades":[...]}.
        This is the only call that actually mutates state -- matching the
        referee exactly, trade for trade, in stamp order."""
        result = self.fold.sweep(record["n"], record["ref"], record["close"],
                                  record.get("owners", []), record.get("trades", []))
        self.last_reference = Decimal(record["ref"])
        return result

    def sync(self, sweep_records: list[dict], seed_px: str | None = None) -> None:
        """Bulk-catch-up from a list of archived sweep records in order."""
        if seed_px is not None and self.fold.global_px is None:
            self.apply_seed({"px": seed_px})
        for record in sweep_records:
            self.apply_sweep_record(record)

    # -- reading live state -----------------------------------------------

    def account(self, did: str):
        return self.fold.accounts.get(did)

    def free_cash(self, did: str) -> Decimal:
        acct = self.account(did)
        return acct.cash if acct else Decimal(0)

    def position(self, did: str) -> Decimal:
        acct = self.account(did)
        return acct.position if acct else Decimal(0)

    # -- the actual guard ---------------------------------------------------

    def would_settle(self, trade: dict, next_sweep_n: int, next_reference: Decimal,
                      assumed_close: Decimal | None = None) -> str | None:
        """Returns the void reason it would get right now, or None if it
        would settle under the estimate described in the module docstring.
        Never mutates state -- safe to call as many times as you like while
        you're still shaping an offer."""
        close = assumed_close if assumed_close is not None else Decimal(trade["px"])
        return self.fold.check(trade, next_sweep_n, next_reference, close)

    def max_affordable_qty(self, did: str, side: str, px: Decimal, fee_rate: Decimal | None = None) -> Decimal:
        """Rough ceiling on how large a NEW (opening) position `did` can take
        at `px` without a `funds` void, ignoring any closing-out of existing
        opposite-side lots (which frees cash instead of costing it -- see
        Account.opening() in the official fold). Conservative: assumes the
        worst-case clawback fee (this sweep's window) rather than the 1% base.
        """
        acct = self.account(did)
        if acct is None:
            return Decimal(0)
        rate = fee_rate if fee_rate is not None else self.fold.fee_rate
        worst_case_fee_rate = max(rate, self.fold.window)  # clawback can reach the full band width
        # cash >= qty*px*(1+worst_case_fee_rate)  =>  qty <= cash / (px*(1+worst_case_fee_rate))
        denom = px * (Decimal(1) + worst_case_fee_rate)
        if denom <= 0:
            return Decimal(0)
        return (acct.cash / denom).quantize(Decimal("0.01"))
