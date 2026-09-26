"""
Sizing and allocation across seats. This does NOT predict NVDA -- that
judgment is yours, and the honest default here is "no edge" (even split).
What this module handles is the mechanical part: turning a conviction level
and a set of independent seats into position sizes that (a) leave headroom
against the funds-check estimate gap in fold_guard.py, and (b) don't reveal
full size in one print, per the visibility argument from the earlier
discussion (d-close1-positions publishes aggregate longs/shorts/top holders
every sweep -- one seat's full size at once is a signal; several partial
tranches across seats and sweeps are not).

Nothing here talks to the network or signs anything.
"""

from __future__ import annotations

import random
from decimal import Decimal, ROUND_DOWN

QTY_STEP = Decimal("0.01")
MIN_QTY = Decimal("0.1")


def safe_size(free_cash: Decimal, px: Decimal, window: Decimal, fee_rate: Decimal,
              headroom: Decimal = Decimal("0.85")) -> Decimal:
    """Max opening quantity at `px`, assuming the worst-case clawback fee
    (the full price-limit window, not just the 1% base) and then only using
    `headroom` (default 85%) of what that leaves -- the buffer that covers
    fold_guard's fee estimate being a lower bound, plus the fact that a
    second trade might clear in the same sweep before yours and change your
    available cash (funds are checked sequentially within a sweep, not
    reserved in advance -- see the fold's own comment on this)."""
    worst_fee_rate = max(fee_rate, window)
    denom = px * (Decimal(1) + worst_fee_rate)
    if denom <= 0:
        return Decimal(0)
    raw = (free_cash * headroom) / denom
    stepped = (raw / QTY_STEP).to_integral_value(rounding=ROUND_DOWN) * QTY_STEP
    return stepped if stepped >= MIN_QTY else Decimal(0)


def entry_schedule(total_qty: Decimal, n_tranches: int) -> list[Decimal]:
    """Split a target size into `n_tranches` pieces, respecting the 0.01 step
    and 0.1 minimum, so you can spread entry over several sweeps instead of
    printing your full size at once."""
    if n_tranches < 1 or total_qty <= 0:
        return []
    per = (total_qty / n_tranches / QTY_STEP).to_integral_value(rounding=ROUND_DOWN) * QTY_STEP
    if per < MIN_QTY:
        # too small to split meaningfully -- one tranche
        return [total_qty] if total_qty >= MIN_QTY else []
    tranches = [per] * (n_tranches - 1)
    remainder = total_qty - per * (n_tranches - 1)
    tranches.append(remainder if remainder >= MIN_QTY else per + remainder)
    return tranches


def barbell_allocation(seat_names: list[str], conviction: float, seed: int = 0) -> dict[str, str]:
    """Assign each seat a side. `conviction` in [0, 1]: 0.5 means no edge
    (roughly even split -- pure breadth, per the convex-payout argument);
    push toward 0 or 1 to weight more seats toward "short" or "long"
    respectively as your actual view warrants. Deterministic given `seed`,
    so you can reason about the split before running anything live."""
    conviction = max(0.0, min(1.0, conviction))
    rng = random.Random(seed)
    return {name: ("long" if rng.random() < conviction else "short") for name in seat_names}


def stagger_seconds(rng: random.Random, low: int = 20, high: int = 240) -> float:
    """A per-action delay so independent seats don't act in visible lockstep
    in the public rooms -- correlated timing is the cheapest way to have
    'independent' bets read as one operator's obvious position."""
    return rng.uniform(low, high)
