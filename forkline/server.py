"""Forkline: a demo food delivery app with planted functional bugs, for checking what the AI QA Scanner finds.

The bugs are listed in BUGS.md (the answer key), which is never served. Comments marking a planted bug (BUG-nn)
only appear in server-side code; the pages and scripts the scanner reads carry none.

Each visitor (cookie) gets a private copy of the demo world, kept in memory, so parallel scans never see each
other's changes. Logging in as the customer or the restaurant owner in the same browser shares that world.
"""

import datetime as dt
import hmac
import html
import json
import math
import os
import re
import secrets
import threading
from collections import OrderedDict
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from . import data
from .data import money

HERE = Path(__file__).resolve().parent
PAGES_DIR = HERE / "pages"
STATIC_DIR = HERE / "static"
STATIC_TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
    ),
}
MAX_BODY = 1024 * 1024
MAX_SESSIONS = 1500
POSTCODE = re.compile(r"FL([1-9]) ?(\d[A-Z]{2})")
TIME = re.compile(r"([01]\d|2[0-3]):(00|30)")
ACTIVE = ("placed", "accepted", "preparing", "out")
LINE_KEYS = ("item", "name", "options", "options_text", "qty", "unit", "total")
NEXT = {"accepted": "preparing", "preparing": "out", "out": "delivered"}

# path -> (page, title, who may open it)
PAGES = {
    "/": ("landing", "Food from local kitchens", None),
    "/login": ("login", "Log in", None),
    "/help": ("help", "Fees and rules", None),
    "/restaurants": ("restaurants", "Restaurants", "customer"),
    "/restaurant": ("restaurant", "Restaurant", "customer"),
    "/cart": ("cart", "Your cart", "customer"),
    "/checkout": ("checkout", "Checkout", "customer"),
    "/orders": ("orders", "Your orders", "customer"),
    "/order": ("order", "Order", "customer"),
    "/account": ("account", "Your account", "customer"),
    "/kitchen": ("kitchen", "Kitchen", "owner"),
    "/manage": ("manage", "Manage restaurant", "owner"),
}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None, second=0, microsecond=0).isoformat()


def _text(body: dict, key: str, limit: int = 200) -> str:
    value = body.get(key, "")
    return value.strip()[:limit] if isinstance(value, str) else ""


def _int(value, message: str) -> int:
    if isinstance(value, bool):
        raise ApiError(400, message)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(400, message) from None


def _number(value, message: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ApiError(400, message)
    return float(value)


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def clock(at: str) -> str:
    """'2026-11-02T09:41:00' -> '9:41'."""
    t = dt.datetime.fromisoformat(at)
    return f"{t.hour}:{t.minute:02d}"


def nice(day: dt.date | str) -> str:
    """'2026-11-03' -> 'Tue 3 Nov'."""
    d = dt.date.fromisoformat(day) if isinstance(day, str) else day
    return f"{d:%a} {d.day} {d:%b}"


def district(postcode: str) -> int:
    return int(postcode[2])


def delivering(r: dict, day: dt.date, hhmm: str) -> bool:
    """Whether a restaurant takes deliveries for a slot starting at hhmm on day."""
    t, opens, closes = minutes(hhmm), minutes(r["open"]), minutes(r["close"])
    service_day = day
    if closes <= opens:
        closes += 24 * 60
        # BUG-23: a slot after midnight isn't counted as part of the night before, so it always looks closed
    if not opens <= t <= closes:  # BUG-22: the last slot should start 30 minutes before closing, not at closing
        return False
    # BUG-25: one-off closures (r["closures"]) are never checked
    return service_day.weekday() not in r["closed_days"]


def hours_text(r: dict) -> str:
    last = (minutes(r["close"]) - data.LAST_SLOT_MINUTES) % (24 * 60)
    return f"{r['open']}–{r['close']} (last slot {last // 60:02d}:{last % 60:02d})"


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.sessions: OrderedDict[str, dict] = OrderedDict()

    def session(self, sid: str | None) -> tuple[str, dict]:
        if sid and sid in self.sessions:
            self.sessions.move_to_end(sid)
            return sid, self.sessions[sid]
        sid = secrets.token_urlsafe(24)
        self.sessions[sid] = {"world": None, "user": None}
        while len(self.sessions) > MAX_SESSIONS:
            self.sessions.popitem(last=False)
        return sid, self.sessions[sid]

    @staticmethod
    def world(sess: dict) -> dict:
        if sess["world"] is None:
            sess["world"] = data.world(today())
        return sess["world"]

    def user(self, sess: dict) -> dict | None:
        if sess["user"] is None:
            return None
        return next((u for u in self.world(sess)["users"] if u["id"] == sess["user"]), None)

    def signed_in(self, sess: dict, role: str = "customer") -> dict:
        user = self.user(sess)
        if not user:
            raise ApiError(401, "Please log in.")
        if user["role"] != role:
            raise ApiError(403, "That is for " + ("customers." if role == "customer" else "restaurant owners."))
        return self.world(sess)

    def me(self, sess: dict) -> dict:
        user = self.user(sess)
        out = {"today": self.world(sess)["today"]}
        return out | {"user": {k: user[k] for k in ("id", "name", "email", "role")} if user else None}

    def login(self, sess: dict, body: dict) -> dict:
        w = self.world(sess)
        email = _text(body, "email").lower()
        u = next((u for u in w["users"] if u["email"] == email), None)
        password = body.get("password")
        if not (u and u["hash"] and isinstance(password, str)) or not hmac.compare_digest(
            u["hash"], data.password_hash(password, bytes.fromhex(u["salt"]))
        ):
            raise ApiError(401, "Incorrect email or password.")
        sess["user"] = u["id"]
        return self.me(sess)

    # lookups

    @staticmethod
    def restaurant(w: dict, rid: int) -> dict:
        found = next((r for r in w["restaurants"] if r["id"] == rid), None)
        if not found:
            raise ApiError(404, "We couldn't find that restaurant.")
        return found

    @staticmethod
    def menu_item(w: dict, iid: int) -> tuple[dict, dict]:
        for r in w["restaurants"]:
            for it in r["menu"]:
                if it["id"] == iid:
                    return r, it
        raise ApiError(404, "We couldn't find that dish.")

    @staticmethod
    def address(w: dict, user: dict, aid) -> dict:
        found = next((a for a in w["addresses"] if a["id"] == aid and a["user"] == user["id"]), None)
        if not found:
            raise ApiError(400, "Choose where to deliver to.")
        return found

    @staticmethod
    def address_text(a: dict) -> str:
        return f"{a['street']}, {a['postcode']}"

    def card(self, r: dict, a: dict) -> dict:
        km = r["km"][district(a["postcode"]) - 1]
        keys = ("id", "name", "cuisine", "rating", "ratings", "eta", "min_order", "open", "close", "closed_days",
                "closures", "blurb")  # fmt: skip
        return {k: r[k] for k in keys} | {"km": km, "fee": self.fee(km), "hours": hours_text(r)}

    @staticmethod
    def fee(km: float) -> float | None:
        if km <= 2.0:
            return 1.49
        if km < 5.0:  # BUG-02: exactly 5.0 km falls into the next tier
            return 2.99
        if km <= 8.0:
            return 4.49
        return None

    # browsing

    def restaurants(self, sess: dict, query: dict) -> dict:
        w = self.signed_in(sess)
        user = self.user(sess)
        a = self.address(w, user, w["cart"]["address"])
        q = (query.get("q") or [""])[0].strip().lower()
        cuisine = (query.get("cuisine") or [""])[0]
        rows = w["restaurants"]
        if q:
            # BUG-01: dish names aren't searched, only the restaurant's name and cuisine
            rows = [r for r in rows if q in r["name"].lower() or q in r["cuisine"].lower()]
        if cuisine:
            rows = [r for r in rows if r["cuisine"] == cuisine]
        return {
            "restaurants": [self.card(r, a) for r in rows],
            "cuisines": sorted({r["cuisine"] for r in w["restaurants"]}),
            "addresses": self.addresses(w, user),
            "address": a["id"],
            "today": w["today"],
        }

    @staticmethod
    def addresses(w: dict, user: dict) -> list[dict]:
        return [a | {"text": Store.address_text(a)} for a in w["addresses"] if a["user"] == user["id"]]

    def choose_address(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        a = self.address(w, self.user(sess), body.get("address"))
        w["cart"]["address"] = a["id"]
        return {"address": a["id"]}

    def restaurant_page(self, sess: dict, rid: int) -> dict:
        w = self.signed_in(sess)
        r = self.restaurant(w, rid)
        a = self.address(w, self.user(sess), w["cart"]["address"])
        reviews = sorted((v for v in w["reviews"] if v["restaurant"] == rid), key=lambda v: v["date"], reverse=True)
        return self.card(r, a) | {
            "menu": r["menu"],
            "reviews": [{k: v[k] for k in ("name", "stars", "comment", "date")} for v in reviews],
            "address": self.address_text(a),
            "cart": self.cart_brief(w),
        }

    # cart

    @staticmethod
    def cart_brief(w: dict) -> dict:
        cart = w["cart"]
        name = next((r["name"] for r in w["restaurants"] if r["id"] == cart["restaurant"]), None)
        return {"restaurant": cart["restaurant"], "restaurant_name": name, "count": Store.count(w)}

    def priced_lines(self, w: dict) -> list[dict]:
        out = []
        for line in w["cart"]["lines"]:
            r, it = self.menu_item(w, line["item"])
            base = line["base"]  # BUG-15: the price saved when the dish was added, not the menu's current price
            extras = data.options_price(it, line["options"])
            unit = money(base + extras)
            total = base * line["qty"] + extras  # BUG-04: option prices are charged once, not for every item
            # BUG-07: the 2-for-1 offer (every second portion free) is never taken off
            out.append(
                {
                    "id": line["id"],
                    "item": it["id"],
                    "restaurant": r["id"],
                    "name": it["name"],
                    "options": line["options"],
                    "options_text": data.options_text(it, line["options"]),
                    "offer": it["offer"],
                    "qty": line["qty"],
                    "unit": unit,
                    "total": money(total),
                }
            )
        return out

    def quote(self, w: dict, user: dict, address: dict, tip=None, use_points: bool = False) -> dict:
        cart = w["cart"]
        lines = self.priced_lines(w)
        r = self.restaurant(w, cart["restaurant"]) if cart["restaurant"] else None
        food = money(sum(x["total"] for x in lines))
        discounts, notes = [], []
        for code in cart["promos"]:
            p = next(p for p in w["promos"] if p["code"] == code)
            if food < p["min_spend"]:
                notes.append(f"{code} needs £{p['min_spend']:.2f} of food.")
                continue
            if p["kind"] == "percent":
                off = food * p["value"] / 100  # BUG-17: the "up to" cap isn't applied
            else:
                off = p["value"]
            discounts.append({"code": code, "amount": money(off)})
        discount = money(min(sum(d["amount"] for d in discounts), food))
        km = r["km"][district(address["postcode"]) - 1] if r else 0.0
        delivery = (self.fee(km) or 0.0) if r else 0.0
        service = money(max(food * data.SERVICE_RATE, data.SERVICE_MIN)) if lines else 0.0  # BUG-10: no £2.50 cap
        small = data.SMALL_ORDER_FEE if lines and food < data.SMALL_ORDER_UNDER else 0.0
        blocks = min(user["points"] // data.POINTS_BLOCK, math.floor(food - discount)) if use_points else 0
        points_off = float(max(blocks, 0))
        if isinstance(tip, dict) and tip.get("percent") in data.TIP_RATES:
            # BUG-11: the percentage is worked out on the food plus fees, not on the food alone
            tip_amount = money((food + delivery + service + small) * tip["percent"] / 100)
        elif isinstance(tip, dict) and "amount" in tip:
            tip_amount = _number(tip["amount"], "Enter a tip in pounds and pence.")
            if not 0 <= tip_amount <= data.TIP_MAX or money(tip_amount) != tip_amount:
                raise ApiError(400, "Tips can be from £0 to £50, in pounds and pence.")
        else:
            tip_amount = 0.0
        total = food - discount - points_off + delivery + service + small + tip_amount
        return {
            "lines": lines,
            "restaurant": self.card(r, address) if r else None,
            "food": food,
            "discounts": discounts,
            "discount": discount,
            "notes": notes,
            "points_used": int(points_off) * data.POINTS_BLOCK,
            "points_off": points_off,
            "points_balance": user["points"],
            "km": km,
            "delivery": delivery,
            "service": service,
            "small_order": small,
            "tip": tip_amount,
            "total": money(total),
        }

    def cart(self, sess: dict) -> dict:
        w = self.signed_in(sess)
        user = self.user(sess)
        a = self.address(w, user, w["cart"]["address"])
        return self.quote(w, user, a) | {"promos": w["cart"]["promos"], "address": a["id"], "count": self.count(w)}

    @staticmethod
    def count(w: dict) -> int:
        return sum(x["qty"] for x in w["cart"]["lines"])

    def add_line(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        cart = w["cart"]
        r, it = self.menu_item(w, _int(body.get("item"), "Choose a dish."))
        qty = _int(body.get("qty", 1), "Choose how many.")
        if not 1 <= qty <= data.MAX_QTY:
            raise ApiError(400, "You can order 1 to 20 of each dish.")
        # BUG-14: sold-out dishes aren't refused
        chosen = body.get("options") if isinstance(body.get("options"), dict) else {}
        options = {}
        for group in it["options"]:
            valid = {c["id"] for c in group["choices"]}
            picked = chosen.get(group["id"])
            if group["type"] == "one":
                if picked in valid:
                    options[group["id"]] = picked
                # BUG-06: a required choice left empty isn't refused
            else:
                picked = [p for p in picked if p in valid] if isinstance(picked, list) else []
                options[group["id"]] = list(dict.fromkeys(picked))  # BUG-05: the "up to" limit isn't checked
        if body.get("replace"):
            cart.update(restaurant=None, lines=[], promos=[])
        # BUG-08: a dish from another restaurant joins the current cart instead of asking to start a new one
        if cart["restaurant"] is None:
            cart["restaurant"] = r["id"]
        same = next((x for x in cart["lines"] if x["item"] == it["id"] and x["options"] == options), None)
        if same:
            same["qty"] = min(same["qty"] + qty, data.MAX_QTY)
        else:
            cart["lines"].append(
                {"id": w["next_id"], "item": it["id"], "qty": qty, "options": options, "base": it["price"]}
            )
            w["next_id"] += 1
        return self.cart(sess)

    def set_qty(self, sess: dict, lid: int, body: dict) -> dict:
        w = self.signed_in(sess)
        cart = w["cart"]
        line = next((x for x in cart["lines"] if x["id"] == lid), None)
        if not line:
            raise ApiError(404, "That dish isn't in your cart.")
        qty = _int(body.get("qty"), "Enter how many you'd like.")
        if qty > data.MAX_QTY:  # BUG-09: zero is a removal, but negative quantities are kept
            raise ApiError(400, "You can order 1 to 20 of each dish.")
        if qty == 0:
            cart["lines"].remove(line)
        else:
            line["qty"] = qty
        if not cart["lines"]:
            cart.update(restaurant=None, promos=[])
        return self.cart(sess)

    def apply_promo(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        cart = w["cart"]
        code = _text(body, "code", 30).upper()
        p = next((p for p in w["promos"] if p["code"] == code), None)
        if not p:
            raise ApiError(400, "We don't recognise that code.")
        yesterday = (dt.date.fromisoformat(w["today"]) - dt.timedelta(days=1)).isoformat()
        if p["until"] < yesterday:  # BUG-19: a code still works the day after its last day
            raise ApiError(400, f"{code} ended on {nice(p['until'])}.")
        if not cart["lines"]:
            raise ApiError(400, "Add some dishes first.")
        food = money(sum(x["total"] for x in self.priced_lines(w)))
        if food < p["min_spend"]:
            raise ApiError(400, f"{code} needs £{p['min_spend']:.2f} of food.")
        # BUG-16: "first order only" codes aren't checked against the customer's earlier orders
        if code in cart["promos"]:
            raise ApiError(400, f"{code} is already on this order.")
        cart["promos"].append(code)  # BUG-18: a second code is added on top instead of refused
        return self.cart(sess)

    def remove_promo(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        code = _text(body, "code", 30).upper()
        if code in w["cart"]["promos"]:
            w["cart"]["promos"].remove(code)
        return self.cart(sess)

    # checkout and orders

    def checkout_quote(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        user = self.user(sess)
        a = self.address(w, user, body.get("address", w["cart"]["address"]))
        w["cart"]["address"] = a["id"]
        q = self.quote(w, user, a, body.get("tip"), bool(body.get("use_points")))
        return q | {"addresses": self.addresses(w, user), "address": a["id"], "today": w["today"]}

    def place_order(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        user = self.user(sess)
        cart = w["cart"]
        if not cart["lines"]:
            raise ApiError(400, "Your cart is empty.")
        a = self.address(w, user, body.get("address"))
        r = self.restaurant(w, cart["restaurant"])
        q = self.quote(w, user, a, body.get("tip"), bool(body.get("use_points")))
        if q["restaurant"]["fee"] is None:
            raise ApiError(400, f"{r['name']} is too far away to deliver to {a['postcode']} (over 8 km).")
        if q["food"] + q["delivery"] < r["min_order"]:  # BUG-13: the delivery fee counts towards the minimum
            raise ApiError(400, f"{r['name']} needs a minimum order of £{r['min_order']:.2f} of food.")
        try:
            slot_day = dt.date.fromisoformat(str(body.get("date")))
        except ValueError:
            raise ApiError(400, "Choose a delivery day.") from None
        slot_time = str(body.get("time") or "")
        if not TIME.fullmatch(slot_time):
            raise ApiError(400, "Choose a delivery time.")
        ahead = (slot_day - dt.date.fromisoformat(w["today"])).days
        if ahead < 1:  # BUG-24: days more than a week ahead aren't refused
            raise ApiError(400, "Choose a day from tomorrow onwards.")
        if not delivering(r, slot_day, slot_time):
            raise ApiError(400, f"{r['name']} isn't delivering at {slot_time} on {nice(slot_day)}.")
        when = now_iso()
        oid = w["next_order"]
        w["next_order"] += 1
        order = {
            "id": oid,
            "user": user["id"],
            "restaurant": r["id"],
            "address": a["id"],
            "slot_date": slot_day.isoformat(),
            "slot_time": slot_time,
            "lines": [{k: x[k] for k in LINE_KEYS} for x in q["lines"]],
            "status": "placed",
            "events": [{"status": "placed", "at": when}],
            "food": q["food"],
            "discount": q["discount"],
            "promos": [d["code"] for d in q["discounts"]],
            "points_used": q["points_used"],
            "points_off": q["points_off"],
            "delivery": q["delivery"],
            "service": q["service"],
            "small_order": q["small_order"],
            "tip": q["tip"],
            "total": q["total"],
            "points_earned": 0,
            "refunds": [],
            "placed": when,
            "delivered_at": None,
        }  # fmt: skip
        # BUG-20: the points used aren't taken off the customer's balance
        w["orders"].append(order)
        cart.update(restaurant=None, lines=[], promos=[])
        return {"id": oid}

    def order_view(self, w: dict, o: dict) -> dict:
        r = self.restaurant(w, o["restaurant"])
        a = next(x for x in w["addresses"] if x["id"] == o["address"])
        customer = next(u for u in w["users"] if u["id"] == o["user"])
        reviews = [v for v in w["reviews"] if v["order"] == o["id"]]
        return o | {
            "restaurant_name": r["name"],
            "address_text": self.address_text(a),
            "customer": customer["name"],
            "events": [e | {"time": clock(e["at"])} for e in o["events"]],
            "vat": money((o["food"] - o["discount"]) * 0.2),  # BUG-32: VAT included is a sixth, not 20%
            "can_cancel": o["status"] in ACTIVE,  # BUG-31: only "placed" orders should be cancellable
            "reviews": [{k: v[k] for k in ("stars", "comment", "date")} for v in reviews],
            "items": sum(x["qty"] for x in o["lines"]),
        }

    def orders(self, sess: dict) -> dict:
        w = self.signed_in(sess)
        user = self.user(sess)
        mine = [o for o in w["orders"] if o["user"] == user["id"]]
        mine.sort(key=lambda o: o["placed"], reverse=True)
        return {"orders": [self.order_view(w, o) for o in mine]}

    def find_order(self, w: dict, oid: int) -> dict:
        o = next((o for o in w["orders"] if o["id"] == oid), None)
        if not o:
            raise ApiError(404, "We couldn't find that order.")
        return o

    def order(self, sess: dict, oid: int) -> dict:
        w = self.signed_in(sess)
        o = self.find_order(w, oid)  # BUG-27: anyone's order opens, not only the customer's own
        return self.order_view(w, o)

    def own_order(self, sess: dict, oid: int) -> tuple[dict, dict]:
        w = self.signed_in(sess)
        o = self.find_order(w, oid)
        if o["user"] != self.user(sess)["id"]:
            raise ApiError(404, "We couldn't find that order.")
        return w, o

    def cancel_order(self, sess: dict, oid: int) -> dict:
        w, o = self.own_order(sess, oid)
        if o["status"] not in ACTIVE:  # BUG-31: accepted, preparing and out-for-delivery orders can be cancelled
            raise ApiError(409, "This order can't be cancelled any more.")
        o["status"] = "cancelled"
        o["events"].append({"status": "cancelled", "at": now_iso()})
        return self.order_view(w, o)

    def reorder(self, sess: dict, oid: int) -> dict:
        w, o = self.own_order(sess, oid)
        cart = w["cart"]
        cart.update(restaurant=o["restaurant"], lines=[], promos=[])
        for x in o["lines"]:
            _, it = self.menu_item(w, x["item"])
            # BUG-30: the dish's sizes and extras aren't copied over
            line = {"id": w["next_id"], "item": it["id"], "qty": x["qty"], "options": {}, "base": it["price"]}
            cart["lines"].append(line)
            w["next_id"] += 1
        return self.cart(sess)

    def review(self, sess: dict, oid: int, body: dict) -> dict:
        w, o = self.own_order(sess, oid)
        stars = body.get("stars")
        if isinstance(stars, bool) or not isinstance(stars, int) or not 1 <= stars <= 5:
            raise ApiError(400, "Choose 1 to 5 stars.")
        comment = _text(body, "comment", 500)
        # BUG-33: orders that haven't been delivered can be reviewed
        # BUG-34: an order can be reviewed more than once
        user = self.user(sess)
        w["reviews"].append(
            {
                "id": w["next_id"],
                "restaurant": o["restaurant"],
                "order": o["id"],
                "user": user["id"],
                "name": user["name"].split()[0],
                "stars": stars,
                "comment": comment,
                "date": w["today"],
            }
        )
        w["next_id"] += 1
        return self.order_view(w, o)

    def missing(self, sess: dict, oid: int, body: dict) -> dict:
        w, o = self.own_order(sess, oid)
        if o["status"] != "delivered":
            raise ApiError(400, "You can report missing items once your order is delivered.")
        # BUG-36: the 48-hour window after delivery isn't checked
        index = _int(body.get("line"), "Choose the missing dish.")
        if not 0 <= index < len(o["lines"]):
            raise ApiError(400, "Choose the missing dish.")
        line = o["lines"][index]
        qty = _int(body.get("qty"), "Enter how many were missing.")
        if qty < 1:  # BUG-35: more than were ordered (less any already refunded) can be claimed
            raise ApiError(400, "Enter how many were missing.")
        each = line["total"] / line["qty"]
        amount = money(each * qty)
        o["refunds"].append({"line": index, "name": line["name"], "qty": qty, "amount": amount, "date": w["today"]})
        return self.order_view(w, o)

    # account

    def account(self, sess: dict) -> dict:
        w = self.signed_in(sess)
        user = self.user(sess)
        return {
            "name": user["name"],
            "email": user["email"],
            "points": user["points"],
            "history": sorted(user["history"], key=lambda h: h["date"], reverse=True),
            "addresses": self.addresses(w, user),
        }

    def add_address(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        user = self.user(sess)
        label = _text(body, "label", 30) or "Other"
        street = _text(body, "street", 80)
        if not street:
            raise ApiError(400, "Enter the street address.")
        m = POSTCODE.fullmatch(_text(body, "postcode", 10).upper())
        if not m:
            raise ApiError(400, "Enter a Forkline postcode, like FL2 4QT.")
        # BUG-26: postcodes outside the delivery area (FL1 to FL6) are accepted
        a = {"id": w["next_id"], "user": user["id"], "label": label, "street": street,
             "postcode": f"FL{m.group(1)} {m.group(2)}"}  # fmt: skip
        w["next_id"] += 1
        w["addresses"].append(a)
        return self.account(sess)

    # restaurant owners

    def managed(self, w: dict, user: dict) -> list[dict]:
        return [r for r in w["restaurants"] if user["id"] in r["managers"]]

    def kitchen(self, sess: dict, rid: int | None) -> dict:
        w = self.signed_in(sess, "owner")
        user = self.user(sess)
        mine = self.managed(w, user)
        r = self.restaurant(w, rid) if rid else mine[0]  # BUG-37: any restaurant's orders open, not only yours
        rows = [o for o in w["orders"] if o["restaurant"] == r["id"]]
        live = sorted((o for o in rows if o["status"] in ACTIVE), key=lambda o: (o["slot_date"], o["slot_time"]))
        done = sorted((o for o in rows if o["status"] not in ACTIVE), key=lambda o: o["placed"], reverse=True)
        return {
            "restaurant": {"id": r["id"], "name": r["name"]},
            "mine": [{"id": x["id"], "name": x["name"]} for x in mine],
            "orders": [self.order_view(w, o) for o in live + done[:8]],
        }

    def kitchen_action(self, sess: dict, oid: int, body: dict) -> dict:
        w = self.signed_in(sess, "owner")
        o = self.find_order(w, oid)  # BUG-37: orders of restaurants you don't manage can be changed too
        action = body.get("action")
        if action in ("accept", "reject"):
            if o["status"] != "placed":
                raise ApiError(409, "That order has already been answered.")
            o["status"] = "accepted" if action == "accept" else "rejected"
        elif action == "next":
            if o["status"] not in NEXT:
                raise ApiError(409, "That order can't move on.")
            o["status"] = NEXT[o["status"]]
        else:
            raise ApiError(400, "Choose what to do with the order.")
        stamp = now_iso()
        o["events"].append({"status": o["status"], "at": stamp})
        if o["status"] == "delivered":
            o["delivered_at"] = stamp
            customer = next(u for u in w["users"] if u["id"] == o["user"])
            earned = math.floor(o["total"])  # BUG-21: points are earned on the whole total, tip and fees included
            o["points_earned"] = earned
            customer["points"] += earned
            customer["history"].append({"date": w["today"], "points": earned, "what": f"Order #{o['id']} delivered"})
        return self.kitchen(sess, o["restaurant"])

    def owned(self, sess: dict, rid) -> tuple[dict, dict]:
        w = self.signed_in(sess, "owner")
        mine = self.managed(w, self.user(sess))
        if rid in (None, ""):
            return w, mine[0]
        r = self.restaurant(w, _int(rid, "Choose a restaurant."))
        if r not in mine:
            raise ApiError(403, "You don't manage that restaurant.")
        return w, r

    def report_rows(self, w: dict, r: dict, day: str) -> list[dict]:
        return sorted(
            (o for o in w["orders"] if o["restaurant"] == r["id"] and o["slot_date"] == day),
            key=lambda o: (o["slot_time"], o["id"]),
        )

    def manage(self, sess: dict, rid, day: str = "") -> dict:
        w, r = self.owned(sess, rid)
        try:
            day = dt.date.fromisoformat(day).isoformat() if day else ""
        except ValueError:
            raise ApiError(400, "Choose a day.") from None
        day = day or (dt.date.fromisoformat(w["today"]) - dt.timedelta(days=1)).isoformat()
        done = [o for o in self.report_rows(w, r, day) if o["status"] not in ("rejected", "cancelled")]
        mine = self.managed(w, self.user(sess))
        return {
            "restaurant": {k: r[k] for k in ("id", "name", "open", "close", "closed_days")} | {"hours": hours_text(r)},
            "mine": [{"id": x["id"], "name": x["name"]} for x in mine],
            "menu": r["menu"],
            "report": {"date": day, "orders": len(done), "food": money(sum(o["food"] for o in done))},
            "today": w["today"],
        }

    def edit_item(self, sess: dict, iid: int, body: dict) -> dict:
        w = self.signed_in(sess, "owner")
        r, it = self.menu_item(w, iid)
        w, r = self.owned(sess, r["id"])
        price = _number(body.get("price"), "Enter a price.")  # BUG-39: £0.50 to £100.00 isn't enforced
        if money(price) != price:
            raise ApiError(400, "Prices are in pounds and pence.")
        it["price"] = price
        it["sold_out"] = bool(body.get("sold_out"))
        return self.manage(sess, r["id"])

    def edit_hours(self, sess: dict, body: dict) -> dict:
        w, r = self.owned(sess, body.get("restaurant"))
        opens, closes = str(body.get("open") or ""), str(body.get("close") or "")
        if not (TIME.fullmatch(opens) and TIME.fullmatch(closes)) or opens == closes:
            raise ApiError(400, "Choose opening and closing times on the hour or half hour.")
        closed = body.get("closed_days")
        if not isinstance(closed, list) or not all(isinstance(d, int) and 0 <= d <= 6 for d in closed):
            raise ApiError(400, "Choose the days you're closed.")
        if len(set(closed)) == 7:
            raise ApiError(400, "You can't be closed every day.")
        r.update(open=opens, close=closes, closed_days=sorted(set(closed)))
        return self.manage(sess, r["id"])

    def report_csv(self, sess: dict, rid, day: str) -> bytes:
        w, r = self.owned(sess, rid)
        try:
            day = dt.date.fromisoformat(day).isoformat()
        except ValueError:
            raise ApiError(400, "Choose a day.") from None
        rows = self.report_rows(w, r, day)  # BUG-38: rejected and cancelled orders are included
        lines = ["Order,Slot,Customer,Items,Status,Food (GBP)"]
        for o in rows:
            customer = next(u for u in w["users"] if u["id"] == o["user"])["name"]
            items = "; ".join(f"{x['qty']} x {x['name']}" for x in o["lines"])
            lines.append(f'{o["id"]},{o["slot_time"]},"{customer}","{items}",{o["status"]},{o["food"]:.2f}')
        lines.append(f",,,,Total,{sum(o['food'] for o in rows):.2f}")
        return ("\n".join(lines) + "\n").encode()

    def promos(self, sess: dict) -> dict:
        w = self.world(sess)
        return {"promos": [{k: p[k] for k in ("code", "text", "until", "first_only")} for p in w["promos"]]}


def render(path: str, store: Store, sess: dict, status_page: str | None = None) -> bytes:
    name, title, _ = PAGES[path] if not status_page else (status_page, "Page not found", None)
    if status_page == "403":
        title = "Not for this account"
    user = store.user(sess)
    if not user:
        nav = '<a href="/" data-nav="landing">Home</a><a href="/help" data-nav="help">Fees and rules</a>'
        account = '<a href="/login" id="login-link">Log in</a>'
    else:
        if user["role"] == "customer":
            count = store.count(store.world(sess))
            links = [
                ("/restaurants", "restaurants", "Restaurants"),
                ("/cart", "cart", f'Cart <span class="badge" id="cart-count">{count}</span>'),
                ("/orders", "orders", "Orders"),
            ]
        else:
            links = [("/kitchen", "kitchen", "Kitchen"), ("/manage", "manage", "Menu and hours")]
        nav = "".join(f'<a href="{h}" data-nav="{k}">{t}</a>' for h, k, t in links)
        nav += '<a href="/help" data-nav="help">Fees and rules</a>'
        first = html.escape(user["name"].split()[0])
        account = (
            f'<a href="/account" class="who" data-nav="account">{first}</a>'
            if user["role"] == "customer"
            else f'<span class="who">{first}</span>'
        )
        account += '<button type="button" id="logout" class="link">Log out</button>'
    script = f'<script src="/static/{name}.js" defer></script>' if (STATIC_DIR / f"{name}.js").exists() else ""
    out = (PAGES_DIR / "_layout.html").read_text()
    values = {
        "title": html.escape(title),
        "page": name,
        "role": user["role"] if user else "",
        "nav": nav,
        "account": account,
        "content": (PAGES_DIR / f"{name}.html").read_text(),
        "scripts": script,
    }
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    return out.encode()


def make_handler(store: Store | None = None):
    store = store or Store()
    static = {f.name: f for f in STATIC_DIR.iterdir() if f.is_file() and f.suffix in STATIC_TYPES}

    class Handler(BaseHTTPRequestHandler):
        server_version = "forkline"

        def log_message(self, fmt, *args):
            pass

        def _session(self) -> tuple[str, dict, bool]:
            sid = None
            try:
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                sid = cookie["fk_sid"].value if "fk_sid" in cookie else None
            except CookieError:
                pass
            new_sid, sess = store.session(sid)
            return new_sid, sess, new_sid != sid

        def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
                self.send_header(k, v)
            if self._new_sid:
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                self.send_header("Set-Cookie", f"fk_sid={self._sid}; Path=/; HttpOnly; SameSite=Lax{secure}")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload: dict):
            self._send(status, json.dumps(payload).encode(), "application/json")

        def _body(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(400, "Bad request.") from None
            if length > MAX_BODY:
                raise ApiError(413, "Request too large.")
            raw = self.rfile.read(length) if length > 0 else b""
            try:
                payload = json.loads(raw or b"{}")
            except ValueError:
                raise ApiError(400, "Send JSON.") from None
            if not isinstance(payload, dict):
                raise ApiError(400, "Send a JSON object.")
            return payload

        def do_HEAD(self):
            self._handle("GET")

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def _handle(self, method: str):
            self._sid, self._new_sid = None, False
            url = urlsplit(self.path)
            path = url.path.rstrip("/") or "/"
            query = parse_qs(url.query)
            try:
                if path == "/healthz":
                    return self._send(200, b"ok", "text/plain")
                if path == "/robots.txt":
                    return self._send(200, b"User-agent: *\nAllow: /\n", "text/plain")
                if path.startswith("/static/") and path[8:] in static:
                    f = static[path[8:]]
                    return self._send(200, f.read_bytes(), STATIC_TYPES[f.suffix])
                with store.lock:
                    self._sid, sess, self._new_sid = self._session()
                    if path.startswith("/api/"):
                        body = self._body() if method == "POST" else {}
                        result = self._api(sess, method, path, body, query)
                        if isinstance(result, bytes):
                            extra = {"Content-Disposition": 'attachment; filename="forkline-sales.csv"'}
                            return self._send(200, result, "text/csv; charset=utf-8", extra)
                        return self._json(200, result)
                    if method != "GET":
                        return self._send(405, b"Method not allowed", "text/plain", {"Allow": "GET, HEAD"})
                    if path not in PAGES:
                        return self._send(404, render("/", store, sess, "404"), "text/html; charset=utf-8")
                    role = PAGES[path][2]
                    user = store.user(sess)
                    if role and not user:
                        location = "/login?next=" + quote(self.path, safe="")
                        return self._send(302, b"", "text/plain", {"Location": location})
                    if role and user["role"] != role:
                        return self._send(403, render("/", store, sess, "403"), "text/html; charset=utf-8")
                    return self._send(200, render(path, store, sess), "text/html; charset=utf-8")
            except ApiError as err:
                return self._json(err.status, {"ok": False, "error": str(err)})
            except Exception:
                return self._json(500, {"ok": False, "error": "Internal Server Error"})

        def _api(self, sess: dict, method: str, path: str, body: dict, query: dict):
            q = lambda k: (query.get(k) or [""])[0]  # noqa: E731
            if method == "GET":
                gets = {
                    "/api/me": lambda: store.me(sess),
                    "/api/promos": lambda: store.promos(sess),
                    "/api/restaurants": lambda: store.restaurants(sess, query),
                    "/api/cart": lambda: store.cart(sess),
                    "/api/orders": lambda: store.orders(sess),
                    "/api/account": lambda: store.account(sess),
                    "/api/kitchen": lambda: store.kitchen(sess, int(q("restaurant") or 0)),
                    "/api/manage": lambda: store.manage(sess, q("restaurant"), q("date")),
                    "/api/manage/report.csv": lambda: store.report_csv(sess, q("restaurant"), q("date")),
                }
                if path in gets:
                    return gets[path]()
                routes = (
                    (r"/api/restaurants/(\d+)", lambda i: store.restaurant_page(sess, int(i))),
                    (r"/api/orders/(\d+)", lambda i: store.order(sess, int(i))),
                )
            else:
                posts = {
                    "/api/login": lambda: store.login(sess, body),
                    "/api/logout": lambda: sess.update(user=None) or {"ok": True},
                    "/api/address": lambda: store.choose_address(sess, body),
                    "/api/cart/lines": lambda: store.add_line(sess, body),
                    "/api/cart/promo": lambda: store.apply_promo(sess, body),
                    "/api/cart/promo/remove": lambda: store.remove_promo(sess, body),
                    "/api/quote": lambda: store.checkout_quote(sess, body),
                    "/api/orders": lambda: store.place_order(sess, body),
                    "/api/account/addresses": lambda: store.add_address(sess, body),
                    "/api/manage/hours": lambda: store.edit_hours(sess, body),
                }
                if path in posts:
                    return posts[path]()
                routes = (
                    (r"/api/cart/lines/(\d+)", lambda i: store.set_qty(sess, int(i), body)),
                    (r"/api/orders/(\d+)/cancel", lambda i: store.cancel_order(sess, int(i))),
                    (r"/api/orders/(\d+)/reorder", lambda i: store.reorder(sess, int(i))),
                    (r"/api/orders/(\d+)/review", lambda i: store.review(sess, int(i), body)),
                    (r"/api/orders/(\d+)/missing", lambda i: store.missing(sess, int(i), body)),
                    (r"/api/kitchen/orders/(\d+)", lambda i: store.kitchen_action(sess, int(i), body)),
                    (r"/api/manage/items/(\d+)", lambda i: store.edit_item(sess, int(i), body)),
                )
            for pattern, run in routes:
                m = re.fullmatch(pattern, path)
                if m:
                    return run(m.group(1))
            raise ApiError(404, "Not found.")

    return Handler


def serve(env: dict[str, str] | None = None) -> None:
    env = dict(os.environ if env is None else env)
    port = int(env.get("PORT", "8087"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), make_handler())
    print(f"Forkline listening on :{port}", flush=True)
    httpd.serve_forever()
