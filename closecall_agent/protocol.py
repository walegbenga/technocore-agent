"""
Close Call (season "close-1") message shapes, built exactly to the spec in
close-call-game.md. Two signature layers, don't conflate them:

  1. The technocore.chat post signature: `<room>|<nonce>|<text>`, produced by
     Seat.sign() in identity.py, proves who POSTED a message.
  2. The trade's own maker_sig / taker_sig: `close-1|terms|<terms>` and
     `close-1|accept|<terms>|<taker did>`, produced by Seat.sign_raw() below,
     prove who AGREED to those terms. The referee's fold checks (1); it does
     NOT re-check (2) -- ledger correctness is (1)'s job, deal consent is (2)'s.
     Get (2) wrong and your countersigned trade is just void or disputable.
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_DOWN
from typing import Literal

SEASON = "close-1"
ROOM_MAIN = "close1"
REFEREE_ROOMS = {
    "price": "d-close1-price",
    "flow": "d-close1-flow",
    "positions": "d-close1-positions",
    "pnl": "d-close1-pnl",
    "state": "d-close1-state",
}

PRICE_STEP = Decimal("0.01")
QTY_STEP = Decimal("0.01")
MIN_QTY = Decimal("0.1")


def fmt_amount(value: Decimal) -> str:
    """Two-decimal string, the only shape the fold's `amount()` accepts."""
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_DOWN))


def canonical_terms(id: str, maker: str, side: Literal["buy", "sell"], qty: Decimal,
                     px: Decimal, taker: str, until: int) -> str:
    """Sorted keys, no spaces -- must match this exactly, or the maker's
    signature won't verify against what the referee reconstructs."""
    obj = {
        "id": id,
        "maker": maker,
        "px": fmt_amount(px),
        "qty": fmt_amount(qty),
        "side": side,
        "taker": taker,
        "until": until,
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sign_maker_terms(seat, terms_json: str) -> str:
    return seat.sign_raw(f"{SEASON}|terms|{terms_json}")


def sign_taker_accept(seat, terms_json: str, taker_did: str) -> str:
    return seat.sign_raw(f"{SEASON}|accept|{terms_json}|{taker_did}")


def build_owner_message(did: str) -> str:
    return json.dumps({"t": "owner", "season": SEASON, "key": did}, separators=(",", ":"))


def build_room_message(room: str) -> str:
    return json.dumps({"t": "room", "season": SEASON, "room": room}, separators=(",", ":"))


def build_trade_message(terms_json: str, taker_did: str, maker_sig: str, taker_sig: str) -> str:
    terms_obj = json.loads(terms_json)
    return json.dumps(
        {"t": "trade", "season": SEASON, "terms": terms_obj, "taker": taker_did,
         "maker_sig": maker_sig, "taker_sig": taker_sig},
        separators=(",", ":"),
    )


def make_offer(seat, id: str, side: Literal["buy", "sell"], qty: Decimal, px: Decimal,
                taker: str, until: int) -> dict:
    """Build a fully-signed maker offer ready to post to close1 (or your own
    room). Returns the pieces you need both to post and to hand to a
    counterparty for countersigning -- nothing here talks to the network."""
    terms_json = canonical_terms(id, seat.did, side, qty, px, taker, until)
    return {
        "terms_json": terms_json,
        "terms_obj": json.loads(terms_json),
        "maker_sig": sign_maker_terms(seat, terms_json),
        "maker": seat.did,
    }


def accept_offer(seat, terms_json: str) -> str:
    """Countersign someone else's offer as `seat`. Returns the taker_sig;
    combine with build_trade_message() to post the completed trade."""
    return sign_taker_accept(seat, terms_json, seat.did)


# ---- open-offer convention -------------------------------------------------
# The spec defines the completed, both-signed {"t":"trade",...} shape, but
# leaves "negotiate however you like" open for how a maker advertises a
# standing offer before anyone's countersigned it. This is our convention for
# that -- the referee ignores it either way, it's only for discovery. Other
# agents in the wild may use a different shape; scan_for_offers() below is
# the one place you'd extend to also recognise theirs.

def build_offer_message(offer: dict) -> str:
    return json.dumps(
        {"t": "offer", "season": SEASON, "terms": offer["terms_obj"], "maker_sig": offer["maker_sig"]},
        separators=(",", ":"),
    )


def try_parse_offer(obj: dict) -> dict | None:
    if not isinstance(obj, dict) or obj.get("t") != "offer" or obj.get("season") != SEASON:
        return None
    terms = obj.get("terms")
    if not isinstance(terms, dict) or "maker_sig" not in obj:
        return None
    return {"terms_obj": terms, "terms_json": json.dumps(terms, sort_keys=True, separators=(",", ":")),
            "maker_sig": obj["maker_sig"]}


# ---- parsing referee posts -------------------------------------------------

def parse_price(obj: dict) -> dict:
    """{"t":"price","n":..,"ref":{"px":..,"time":..,"tid":..},"limits":[lo,hi],"global":..,"file":..}"""
    return {
        "sweep": obj["n"],
        "reference": Decimal(obj["ref"]["px"]),
        "ref_time": obj["ref"]["time"],
        "ref_trade_id": obj["ref"]["tid"],
        "limits": [Decimal(x) for x in obj.get("limits", [])],
        "global_price": Decimal(obj["global"]) if obj.get("global") else None,
    }


def parse_flow(obj: dict) -> dict:
    """{"t":"flow","n":..,"mints":[..],"rooms":[..],"settled":..,"void":..,"missed":[..],"file":..}"""
    return {
        "sweep": obj["n"],
        "mints": obj.get("mints", []),
        "rooms": obj.get("rooms", []),
        "settled": obj.get("settled"),
        "void": obj.get("void"),
        "missed": obj.get("missed", []),
    }


def parse_positions(obj: dict) -> dict:
    return {"sweep": obj["n"], "open": obj.get("open"), "longs": obj.get("longs"),
            "shorts": obj.get("shorts"), "top": obj.get("top", [])}


def parse_pnl(obj: dict) -> dict:
    return {"sweep": obj["n"], "mark": obj.get("mark"), "top": obj.get("top", [])}


def parse_state(obj: dict) -> dict:
    return {"sweep": obj["n"], "root": obj.get("root"), "owners": obj.get("owners"),
            "rooms": obj.get("rooms")}
