"""Forkline's demo world: restaurants and menus, addresses, orders, reviews, promo codes and points, dated from today.

Every visitor gets a fresh copy (see server.Store), so scans never disturb each other. Seeded orders carry the
totals they were charged at the time, worked out with the published rules.
"""

import datetime as dt
import hashlib
import math

PASSWORD = "Forkline@2026"
SALT = b"forkline-demo-salt"

DELIVERY_TIERS = ((2.0, 1.49), (5.0, 2.99), (8.0, 4.49))
SERVICE_RATE, SERVICE_MIN, SERVICE_MAX = 0.05, 0.50, 2.50
SMALL_ORDER_UNDER, SMALL_ORDER_FEE = 12.0, 1.50
TIP_RATES = (10, 15, 20)
TIP_MAX = 50.0
POINTS_BLOCK = 100
MAX_QTY = 20
SLOT_DAYS = 7
LAST_SLOT_MINUTES = 30
COMPLAINT_HOURS = 48
ZONE = range(1, 7)
PRICE_RANGE = (0.50, 100.0)


def password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 20_000).hex()


DEMO_HASH = password_hash(PASSWORD, SALT)


def money(x: float) -> float:
    return round(x + 1e-9, 2)


def delivery_fee(km: float) -> float | None:
    for limit, fee in DELIVERY_TIERS:
        if km <= limit:
            return fee
    return None


def service_fee(food: float) -> float:
    return money(min(max(food * SERVICE_RATE, SERVICE_MIN), SERVICE_MAX))


SIZE_PIZZA = {
    "id": "size",
    "name": "Size",
    "type": "one",
    "required": True,
    "default": "reg",
    "choices": [
        {"id": "reg", "name": 'Regular (10")', "price": 0.0},
        {"id": "lg", "name": 'Large (13")', "price": 3.0},
    ],
}
TOPPINGS = {
    "id": "top",
    "name": "Extra toppings",
    "type": "many",
    "max": 3,
    "choices": [
        {"id": "mozz", "name": "Mozzarella", "price": 1.2},
        {"id": "olive", "name": "Olives", "price": 0.8},
        {"id": "mush", "name": "Mushrooms", "price": 0.9},
        {"id": "pep", "name": "Pepperoni", "price": 1.5},
        {"id": "rocket", "name": "Rocket", "price": 0.7},
        {"id": "jal", "name": "Jalapeños", "price": 0.6},
    ],
}
FILLING = {
    "id": "filling",
    "name": "Filling",
    "type": "one",
    "required": True,
    "default": None,
    "choices": [
        {"id": "pork", "name": "Braised pork belly", "price": 0.0},
        {"id": "tofu", "name": "Crispy tofu", "price": 0.0},
        {"id": "chicken", "name": "Fried chicken", "price": 0.5},
    ],
}
SPICE = {
    "id": "spice",
    "name": "Spice",
    "type": "one",
    "required": True,
    "default": "med",
    "choices": [
        {"id": "mild", "name": "Mild", "price": 0.0},
        {"id": "med", "name": "Medium", "price": 0.0},
        {"id": "hot", "name": "Hot", "price": 0.0},
    ],
}
SIZE_DRINK = {
    "id": "size",
    "name": "Size",
    "type": "one",
    "required": True,
    "default": "reg",
    "choices": [{"id": "reg", "name": "Regular", "price": 0.0}, {"id": "lg", "name": "Large", "price": 1.0}],
}
BURGER_EXTRAS = {"id": "extra", "name": "Add-ons", "type": "many", "max": 4, "choices": [
    {"id": "cheese", "name": "Cheese", "price": 1.0}, {"id": "bacon", "name": "Bacon", "price": 1.5},
    {"id": "egg", "name": "Fried egg", "price": 1.0}, {"id": "rings", "name": "Onion rings", "price": 1.2},
    {"id": "jal", "name": "Jalapeños", "price": 0.6}]}  # fmt: skip


def item(iid, name, price, desc, options=(), offer=None, veg=False) -> dict:
    return {"id": iid, "name": name, "price": price, "description": desc, "options": [dict(o) for o in options],
            "offer": offer, "veg": veg, "sold_out": False}  # fmt: skip


def restaurants() -> list[dict]:
    return [
        {"id": 1, "name": "Nonna's Oven", "cuisine": "Italian", "rating": 4.6, "ratings": 212, "eta": "25–35 min",
         "min_order": 10.0, "open": "11:30", "close": "22:00", "closed_days": [], "closures": [], "managers": [2],
         "blurb": "Wood-fired pizza from a seventy-year-old family recipe.",
         "km": [1.2, 1.8, 3.4, 4.6, 6.1, 7.0, 8.4, 9.6, 11.0],
         "menu": [
             item(101, "Margherita", 9.5, "Tomato, fior di latte, basil.", (SIZE_PIZZA, TOPPINGS), veg=True),
             item(102, "Diavola", 11.5, "Tomato, mozzarella, spicy salami, chilli oil.", (SIZE_PIZZA, TOPPINGS)),
             item(103, "Garlic bread", 4.0, "With rosemary and sea salt.", veg=True),
             item(104, "Tiramisu", 5.5, "Made in house every morning.", veg=True),
             item(105, "Lemonade", 2.8, "Sicilian lemons, sparkling.", veg=True),
         ]},
        {"id": 2, "name": "Bao Brothers", "cuisine": "Taiwanese", "rating": 4.4, "ratings": 138, "eta": "30–40 min",
         "min_order": 15.0, "open": "12:00", "close": "21:30", "closed_days": [], "closures": [], "managers": [2],
         "blurb": "Fluffy steamed buns, hand-folded dumplings and noodles.",
         "km": [6.2, 5.0, 3.9, 2.4, 1.1, 2.6, 4.0, 5.5, 7.1],
         "menu": [
             item(201, "Gua bao", 6.5, "Steamed bun with pickles, peanut and coriander.", (FILLING,)),
             item(202, "Pork gyoza (6)", 5.5, "Pan-fried, with black vinegar dip.", offer="2 for 1"),
             item(203, "Dan dan noodles", 9.8, "Sesame, chilli and minced pork.", (SPICE,)),
             item(204, "Bubble tea", 4.2, "Brown sugar milk tea with tapioca pearls.", (SIZE_DRINK,), veg=True),
             item(205, "Sesame cucumber", 3.5, "Smashed cucumber, garlic, sesame.", veg=True),
         ]},
        {"id": 3, "name": "Saffron Lane", "cuisine": "Indian", "rating": 4.7, "ratings": 301, "eta": "35–45 min",
         "min_order": 12.0, "open": "17:00", "close": "23:00", "closed_days": [0], "closures": [], "managers": [],
         "blurb": "Slow-cooked curries and naan from the tandoor.",
         "km": [2.9, 3.2, 1.5, 2.2, 4.4, 5.6, 6.8, 8.1, 9.5],
         "menu": [
             item(301, "Chicken tikka masala", 11.9, "Charred chicken in a creamy tomato sauce."),
             item(302, "Chana masala", 9.4, "Chickpeas, tomato, ginger, garam masala.", veg=True),
             item(303, "Garlic naan", 3.2, "From the tandoor.", veg=True),
             item(304, "Pilau rice", 3.4, "Basmati with whole spices.", veg=True),
             item(305, "Mango lassi", 3.6, "Alphonso mango and yoghurt.", veg=True),
         ]},
        {"id": 4, "name": "Late Owl Burgers", "cuisine": "Burgers", "rating": 4.2, "ratings": 176, "eta": "20–30 min",
         "min_order": 10.0, "open": "18:00", "close": "02:00", "closed_days": [], "closures": [], "managers": [],
         "blurb": "Smash burgers and loaded fries until late.",
         "km": [3.1, 2.6, 2.0, 3.3, 4.8, 6.0, 7.2, 8.4, 9.9],
         "menu": [
             item(401, "Owl burger", 10.5, "Double smash patty, pickles, owl sauce.", (BURGER_EXTRAS,)),
             item(402, "Veggie burger", 9.9, "Black bean patty, smoked cheddar.", (BURGER_EXTRAS,), veg=True),
             item(403, "Night fries", 3.9, "Skin-on fries, rosemary salt.", veg=True),
             item(404, "Milkshake", 4.5, "Vanilla, chocolate or salted caramel.", veg=True),
         ]},
        {"id": 5, "name": "Green Fork", "cuisine": "Salads", "rating": 4.5, "ratings": 94, "eta": "15–25 min",
         "min_order": 8.0, "open": "08:00", "close": "16:00", "closed_days": [], "closures": [], "managers": [],
         "blurb": "Grain bowls, wraps and cold-pressed juice.",
         "km": [1.0, 1.4, 2.6, 3.8, 5.3, 6.5, 7.6, 8.9, 10.2],
         "menu": [
             item(501, "Harvest bowl", 8.9, "Roast squash, farro, kale, tahini.", veg=True),
             item(502, "Falafel wrap", 7.4, "Hummus, pickled cabbage, chilli sauce.", veg=True),
             item(503, "Green juice", 3.9, "Apple, cucumber, spinach, lime.", veg=True),
             item(504, "Banana bread", 2.9, "Toasted, with salted butter.", veg=True),
         ]},
        {"id": 6, "name": "Taco Tide", "cuisine": "Mexican", "rating": 4.3, "ratings": 121, "eta": "30–40 min",
         "min_order": 12.0, "open": "12:00", "close": "22:00", "closed_days": [], "closures": [], "managers": [],
         "blurb": "Baja fish tacos and burritos the size of your forearm.",
         "km": [11.2, 9.5, 7.9, 6.0, 4.1, 2.8, 1.9, 3.5, 5.0],
         "menu": [
             item(601, "Fish tacos (3)", 9.6, "Beer-battered cod, slaw, chipotle mayo."),
             item(602, "Chicken burrito", 10.2, "Rice, black beans, pico de gallo."),
             item(603, "Nachos", 6.5, "Cheese, jalapeños, guacamole.", veg=True),
             item(604, "Horchata", 3.2, "Rice, cinnamon and vanilla.", veg=True),
         ]},
        {"id": 7, "name": "Sakura Roll", "cuisine": "Japanese", "rating": 4.8, "ratings": 265, "eta": "25–35 min",
         "min_order": 15.0, "open": "11:00", "close": "22:00", "closed_days": [], "closures": [], "managers": [],
         "blurb": "Sushi, katsu and ramen made to order.",
         "km": [4.0, 3.6, 2.4, 1.6, 2.9, 4.1, 5.4, 6.6, 7.9],
         "menu": [
             item(701, "Salmon nigiri (6)", 8.4, "Scottish salmon on seasoned rice."),
             item(702, "Chicken katsu curry", 11.8, "Panko chicken, curry sauce, rice."),
             item(703, "Vegetable maki (8)", 6.9, "Cucumber, avocado, pickled radish.", veg=True),
             item(704, "Miso soup", 2.6, "Tofu, wakame, spring onion.", veg=True),
             item(705, "Matcha mochi (3)", 4.2, "Soft rice cakes with matcha cream.", veg=True),
         ]},
    ]  # fmt: skip


def options_text(menu_item: dict, chosen: dict) -> str:
    parts = []
    for group in menu_item["options"]:
        picked = chosen.get(group["id"])
        ids = picked if isinstance(picked, list) else [picked] if picked else []
        parts += [c["name"] for c in group["choices"] if c["id"] in ids]
    return ", ".join(parts)


def options_price(menu_item: dict, chosen: dict) -> float:
    total = 0.0
    for group in menu_item["options"]:
        picked = chosen.get(group["id"])
        ids = picked if isinstance(picked, list) else [picked] if picked else []
        total += sum(c["price"] for c in group["choices"] if c["id"] in ids)
    return total


def world(today: dt.date) -> dict:
    """A fresh copy of everything one visitor can see and change."""
    rests = restaurants()
    rests[4]["closures"] = [(today + dt.timedelta(days=3)).isoformat()]
    items = {i["id"]: i for r in rests for i in r["menu"]}
    addresses = [
        {"id": 1, "user": 1, "label": "Home", "street": "14 Larch Road", "postcode": "FL2 4QT"},
        {"id": 2, "user": 1, "label": "Work", "street": "Unit 5, Mill Yard", "postcode": "FL5 1BN"},
        {"id": 3, "user": 3, "label": "Home", "street": "7 Quay Street", "postcode": "FL5 2HD"},
        {"id": 4, "user": 4, "label": "Home", "street": "22 Orchard Way", "postcode": "FL3 8LP"},
        {"id": 5, "user": 5, "label": "Home", "street": "3 Bell Court", "postcode": "FL1 6RE"},
    ]

    def at(days: int, hhmm: str) -> str:
        h, m = map(int, hhmm.split(":"))
        return dt.datetime.combine(today + dt.timedelta(days=days), dt.time(h, m)).isoformat()

    def line(iid: int, qty: int, **chosen) -> dict:
        it = items[iid]
        unit = it["price"] + options_price(it, chosen)
        total = unit * qty - (unit * (qty // 2) if it["offer"] else 0)
        return {"item": iid, "name": it["name"], "options": chosen, "options_text": options_text(it, chosen),
                "qty": qty, "unit": money(unit), "total": money(total)}  # fmt: skip

    orders = []

    def order(oid, user, rid, address, slot, lines, status, events, promo=None, tip=0.0, points=0):
        r = rests[rid - 1]
        district = int(addresses[address - 1]["postcode"][2])
        food = money(sum(x["total"] for x in lines))
        discount = 0.0
        if promo == "FEAST20":
            discount = money(min(food * 0.2, 8.0))
        delivery = delivery_fee(r["km"][district - 1])
        service = service_fee(food)
        small = SMALL_ORDER_FEE if food < SMALL_ORDER_UNDER else 0.0
        tip = money(food * tip / 100) if isinstance(tip, int) else tip
        total = money(food - discount - points / 100 + delivery + service + small + tip)
        names = ("placed", "accepted", "preparing", "out", "delivered")
        evs = [{"status": s, "at": at(*e)} for s, e in zip(names, events, strict=False)]
        if status in ("rejected", "cancelled"):
            evs = [evs[0], {"status": status, "at": at(*events[-1])}]
        earned = math.floor(food - discount) if status == "delivered" else 0
        orders.append({"id": oid, "user": user, "restaurant": rid, "address": address, "slot_date": slot[0],
                       "slot_time": slot[1], "lines": lines, "status": status, "events": evs, "food": food,
                       "discount": discount, "promos": [promo] if promo else [], "points_used": points,
                       "points_off": points / 100, "delivery": delivery, "service": service, "small_order": small,
                       "tip": tip, "total": total, "points_earned": earned, "refunds": [],
                       "placed": evs[0]["at"]})  # fmt: skip

    def day(n: int) -> str:
        return (today + dt.timedelta(days=n)).isoformat()

    order(
        1041,
        1,
        1,
        1,
        (day(-6), "19:00"),
        [line(101, 1, size="lg", top=["olive"]), line(103, 1), line(104, 1)],
        "delivered",
        [(-7, "20:02"), (-7, "20:10"), (-6, "18:31"), (-6, "18:52"), (-6, "19:04")],
        tip=10,
    )
    order(
        1042,
        1,
        7,
        1,
        (day(-3), "19:30"),
        [line(701, 2), line(702, 1), line(704, 2)],
        "delivered",
        [(-4, "12:15"), (-4, "12:20"), (-3, "18:55"), (-3, "19:12"), (-3, "19:33")],
        promo="FEAST20",
    )
    order(
        1043,
        3,
        2,
        3,
        (day(-2), "13:00"),
        [line(203, 1, spice="hot"), line(202, 2), line(201, 1, filling="pork")],
        "delivered",
        [(-3, "17:40"), (-3, "17:52"), (-2, "12:20"), (-2, "12:41"), (-2, "12:58")],
    )
    order(
        1044,
        1,
        5,
        2,
        (day(-1), "10:30"),
        [line(501, 2), line(503, 2)],
        "delivered",
        [(-2, "20:15"), (-2, "20:31"), (-1, "9:41"), (-1, "10:02"), (-1, "10:39")],
        tip=15,
    )
    order(1045, 3, 1, 3, (day(1), "19:30"), [line(102, 2)], "placed", [(0, "8:05")])
    order(1046, 1, 1, 1, (day(1), "18:30"), [line(101, 1), line(104, 1)], "accepted", [(0, "7:48"), (0, "8:02")])
    order(1047, 4, 3, 4, (day(1), "19:00"), [line(301, 2), line(303, 1)], "placed", [(0, "7:30")])
    order(
        1048,
        5,
        1,
        5,
        (day(-1), "19:00"),
        [line(102, 1), line(104, 1)],
        "delivered",
        [(-2, "18:20"), (-2, "18:31"), (-1, "18:25"), (-1, "18:44"), (-1, "18:58")],
        tip=2.0,
    )
    order(1049, 4, 1, 4, (day(-1), "20:00"), [line(101, 2)], "rejected", [(-2, "19:05"), (-2, "19:12")])
    order(1050, 3, 1, 3, (day(-1), "18:30"), [line(102, 1), line(104, 1)], "cancelled", [(-2, "16:40"), (-2, "16:51")])
    order(
        1051,
        5,
        1,
        5,
        (day(-1), "20:30"),
        [line(101, 1, size="lg", top=["pep"]), line(105, 1)],
        "delivered",
        [(-2, "21:10"), (-2, "21:14"), (-1, "19:50"), (-1, "20:12"), (-1, "20:27")],
    )
    for o in orders:
        o["delivered_at"] = next((e["at"] for e in o["events"] if e["status"] == "delivered"), None)

    def review(rid, oid, name, stars, comment, days):
        return {"id": oid or 9000 + rid * 10 + stars, "restaurant": rid, "order": oid, "user": None, "name": name,
                "stars": stars, "comment": comment, "date": day(days)}  # fmt: skip

    reviews = [
        review(1, 1041, "Liv", 4, "Great crust, the olives were a bit sparse.", -6),
        review(1, None, "Tom", 5, "Best Diavola in town, arrived piping hot.", -9),
        review(1, None, "Ana", 4, "Lovely tiramisu.", -15),
        review(2, 1043, "Sam", 5, "The gyoza deal is unbeatable.", -2),
        review(2, None, "Mei", 4, "Bao were fluffy, noodles a little mild.", -12),
        review(3, None, "Priya", 5, "Proper tikka, generous naan.", -5),
        review(4, None, "Joe", 4, "Saved my night shift.", -7),
        review(5, None, "Ruth", 5, "Fresh and filling.", -4),
        review(6, None, "Carl", 4, "Fish tacos were spot on.", -8),
        review(7, None, "Hana", 5, "Katsu curry like in Osaka.", -6),
    ]
    reviews[0]["user"] = 1
    reviews[3]["user"] = 3
    return {
        "today": today.isoformat(),
        "users": [
            {"id": 1, "name": "Liv Brennan", "email": "liv@forkline.test", "role": "customer", "salt": SALT.hex(),
             "hash": DEMO_HASH, "points": 340, "history": [
                 {"date": day(-90), "points": 266, "what": "Points from earlier orders"},
                 {"date": day(-6), "points": 22, "what": "Order #1041 delivered"},
                 {"date": day(-3), "points": 27, "what": "Order #1042 delivered"},
                 {"date": day(-1), "points": 25, "what": "Order #1044 delivered"}]},
            {"id": 2, "name": "Raj Mehta", "email": "raj@forkline.test", "role": "owner", "salt": SALT.hex(),
             "hash": DEMO_HASH, "points": 0, "history": []},
            {"id": 3, "name": "Sam Ortiz", "email": "sam@forkline.test", "role": "customer", "salt": SALT.hex(),
             "hash": "", "points": 0, "history": []},
            {"id": 4, "name": "Priya Shah", "email": "priya@forkline.test", "role": "customer", "salt": SALT.hex(),
             "hash": "", "points": 0, "history": []},
            {"id": 5, "name": "Tom Reed", "email": "tom@forkline.test", "role": "customer", "salt": SALT.hex(),
             "hash": "", "points": 0, "history": []},
        ],
        "restaurants": rests,
        "addresses": addresses,
        "orders": orders,
        "reviews": reviews,
        "promos": [
            {"code": "WELCOME5", "kind": "amount", "value": 5.0, "cap": None, "min_spend": 15.0, "first_only": True,
             "until": day(60), "text": "£5 off your first Forkline order of £15 or more"},
            {"code": "FEAST20", "kind": "percent", "value": 20, "cap": 8.0, "min_spend": 25.0, "first_only": False,
             "until": day(30), "text": "20% off food when you spend £25 or more, up to £8 off"},
            {"code": "LUNCH3", "kind": "amount", "value": 3.0, "cap": None, "min_spend": 12.0, "first_only": False,
             "until": day(-1), "text": "£3 off orders of £12 or more"},
            {"code": "SUMMER10", "kind": "percent", "value": 10, "cap": 5.0, "min_spend": 20.0, "first_only": False,
             "until": day(-70), "text": "10% off food when you spend £20 or more, up to £5 off"},
        ],
        "cart": {"restaurant": None, "lines": [], "promos": [], "address": 1},
        "next_id": 2000,
        "next_order": 1052,
    }  # fmt: skip
