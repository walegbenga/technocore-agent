"""
Orchestrator skeleton for one seat's participation loop. Run one process per
seat (that's what keeps seats operationally independent -- see strategy.py's
stagger_seconds), pointed at its own --seat name.

TWO THINGS ARE DELIBERATELY LEFT AS TODOs rather than guessed:

  1. fetch_archive_file(): the flow room posts a hash, not the sweep's full
     trade list -- you need wherever FLOP Labs serves archived sweep files by
     hash (check the seed message and https://technocore.chat/llms.txt for
     the live endpoint). Until this is wired up, fold_guard can't reconstruct
     exact live balances, only the reference price/band from d-close1-price.
  2. decide_direction(): your actual NVDA view. The default below is the
     "no edge -> spread for breadth" allocation from strategy.py. Replace it
     the moment you have a real opinion.

Everything else here is concrete and matches the published spec.
"""

from __future__ import annotations

import argparse
import random
import time
from decimal import Decimal
from pathlib import Path

import client
import protocol
import strategy
from identity import load_or_create_seat
from fold_guard import LiveFold


def register(seat) -> None:
    text = protocol.build_owner_message(seat.did)
    client.say_signed(seat, protocol.ROOM_MAIN, text)
    print(f"[{seat.name}] registered {seat.did}")


def fetch_archive_file(file_hash: str) -> dict:
    """TODO: wire this to the real archive endpoint (see module docstring).
    Must return the full sweep record: {"n":..,"ref":..,"close":..,
    "owners":[...],"trades":[...]} -- exactly what Fold.sweep() expects."""
    raise NotImplementedError(
        f"no archive endpoint configured for file {file_hash} -- see agent.py's docstring"
    )


def latest_reference(seen_since: int = 0) -> tuple[int, Decimal, Decimal] | None:
    """Poll d-close1-price for the newest post. Returns (sweep_n, reference,
    band_half_width) or None if nothing new. `band_half_width` here is just
    reference * window (0.05 by default) -- exact bounds also come straight
    off `limits` in the post if you'd rather not assume the window."""
    msgs = client.read_room(protocol.REFEREE_ROOMS["price"], since=seen_since, wait=10)
    for m in reversed(msgs):
        obj = m.json
        if obj and obj.get("t") == "price":
            parsed = protocol.parse_price(obj)
            return parsed["sweep"], parsed["reference"], parsed["reference"] * Decimal("0.05")
    return None


def scan_for_offers(desired_position: str, exclude_did: str, since: int = 0) -> list[dict]:
    """desired_position: "long" or "short" -- what YOU want to end up holding.
    Returns parsed offers whose maker side lets you get there by countersigning
    (maker side "sell" -> you'd buy/long; maker side "buy" -> you'd short)."""
    want_maker_side = "sell" if desired_position == "long" else "buy"
    msgs = client.read_room(protocol.ROOM_MAIN, since=since, limit=200)
    hits = []
    for m in msgs:
        obj = m.json
        offer = protocol.try_parse_offer(obj) if obj else None
        if offer and offer["terms_obj"].get("side") == want_maker_side and offer["terms_obj"].get("maker") != exclude_did:
            hits.append(offer)
    return hits


def accept(seat, offer: dict, guard: LiveFold, next_sweep_n: int, reference: Decimal) -> bool:
    terms = offer["terms_obj"]
    trade_dict = {**terms, "countersigner": seat.did}
    reason = guard.would_settle(trade_dict, next_sweep_n, reference)
    if reason is not None:
        print(f"[{seat.name}] skipping offer {terms['id']}: would go void ({reason})")
        return False
    taker_sig = protocol.accept_offer(seat, offer["terms_json"])
    text = protocol.build_trade_message(offer["terms_json"], seat.did, offer["maker_sig"], taker_sig)
    client.say_signed(seat, protocol.ROOM_MAIN, text)
    print(f"[{seat.name}] accepted {terms['id']} ({terms['side']} {terms['qty']} @ {terms['px']})")
    return True


def post_own_offer(seat, side: str, qty: Decimal, px: Decimal, until_sweep: int, offer_id: str) -> dict:
    offer = protocol.make_offer(seat, offer_id, side, qty, px, "any", until_sweep)
    client.say_signed(seat, protocol.ROOM_MAIN, protocol.build_offer_message(offer))
    print(f"[{seat.name}] posted offer {offer_id}: {side} {qty} @ {px}, good through sweep {until_sweep}")
    return offer


def run(seat_name: str, keydir: str, conviction: float, loop_delay: int) -> None:
    seat = load_or_create_seat(seat_name, keydir)
    register(seat)
    guard = LiveFold()
    rng = random.Random(hash(seat.did) & 0xFFFFFFFF)

    position = strategy.barbell_allocation([seat.name], conviction, seed=hash(seat.did))[seat.name]
    print(f"[{seat.name}] target position this run: {position}")

    seen_price_seq = 0
    while True:
        latest = latest_reference(seen_price_seq)
        if latest is None:
            time.sleep(loop_delay)
            continue
        sweep_n, reference, _band = latest

        # TODO once fetch_archive_file is wired: guard.apply_sweep_record(fetch_archive_file(file_hash))
        # so guard.free_cash(seat.did) reflects real, referee-confirmed balance
        # before every size decision -- without it, only price/band tracking works.

        offers = scan_for_offers(position, exclude_did=seat.did)
        took_one = False
        for offer in offers:
            time.sleep(strategy.stagger_seconds(rng))
            if accept(seat, offer, guard, sweep_n + 1, reference):
                took_one = True
                break

        if not took_one and rng.random() < 0.3:  # don't post every idle cycle -- avoid looking bot-obvious
            side = "buy" if position == "long" else "sell"
            px = reference  # replace with your actual entry logic
            offer_id = f"{seat.name[:4]}{sweep_n}"[:16]
            post_own_offer(seat, side, Decimal("0.5"), px, sweep_n + 12, offer_id)

        time.sleep(loop_delay)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Close Call seat runner")
    p.add_argument("--seat", required=True, help="seat name, e.g. seat-a")
    p.add_argument("--keydir", default="./keys")
    p.add_argument("--conviction", type=float, default=0.5, help="0=all short, 1=all long, 0.5=no edge")
    p.add_argument("--loop-delay", type=int, default=30)
    args = p.parse_args()
    run(args.seat, args.keydir, args.conviction, args.loop_delay)
