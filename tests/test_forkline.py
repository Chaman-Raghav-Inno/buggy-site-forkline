"""Forkline's server-side planted bugs stay planted (BUGS.md) and nothing it serves gives them away."""

import datetime as dt
import http.cookiejar
import json
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

import pytest

from forkline import data, server

T = server.today()


def day(n: int) -> str:
    return (T + dt.timedelta(days=n)).isoformat()


def next_weekday(weekday: int, start: int = 1) -> str:
    d = T + dt.timedelta(days=start)
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    return d.isoformat()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, base: str):
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())

    def request(self, path: str, body=None) -> tuple[int, bytes, dict]:
        payload = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=payload, headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as err:
            return err.code, err.read(), dict(err.headers)

    def get(self, path: str, **query):
        status, raw, _ = self.request(path + ("?" + urlencode(query) if query else ""))
        return status, json.loads(raw)

    def post(self, path: str, body: dict | None = None):
        status, raw, _ = self.request(path, body or {})
        return status, json.loads(raw)

    def login(self, who: str, password: str = data.PASSWORD) -> int:
        return self.post("/api/login", {"email": f"{who}@forkline.test", "password": password})[0]

    def add(self, item: int, qty: int = 1, replace: bool = False, **options):
        return self.post("/api/cart/lines", {"item": item, "qty": qty, "options": options, "replace": replace})

    def order(self, date: str | None = None, time: str = "19:00", address: int = 1, **extra):
        body = {"address": address, "date": date or day(1), "time": time} | extra
        return self.post("/api/orders", body)


@pytest.fixture
def base_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(server.Store()))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def liv(base_url):
    c = Client(base_url)
    assert c.login("liv") == 200
    return c


@pytest.fixture
def raj(base_url):
    c = Client(base_url)
    assert c.login("raj") == 200
    return c


def test_pages_and_access(base_url, liv, raj):
    visitor = Client(base_url)
    for path in ("/", "/help", "/login"):
        assert visitor.request(path)[0] == 200, path
    status, _, headers = visitor.request("/restaurants")
    assert status == 302 and headers["Location"] == "/login?next=%2Frestaurants"
    assert visitor.request("/nope")[0] == 404 and visitor.request("/healthz")[1] == b"ok"
    assert visitor.get("/api/promos")[0] == 200 and visitor.get("/api/cart")[0] == 401
    assert liv.request("/kitchen")[0] == 403 and liv.get("/api/kitchen")[0] == 403
    assert raj.request("/cart")[0] == 403 and raj.get("/api/manage", restaurant=3)[0] == 403
    for path in ("/restaurants", "/restaurant?id=1", "/cart", "/checkout", "/orders", "/order?id=1041", "/account"):
        assert liv.request(path)[0] == 200, path
    for path in ("/kitchen", "/kitchen?restaurant=2", "/manage", "/help"):
        assert raj.request(path)[0] == 200, path
    assert Client(base_url).login("sam", "") == 401


def test_answer_key_is_never_served_or_hinted(base_url):
    visitor = Client(base_url)
    for path in ("/BUGS.md", "/static/../BUGS.md", "/server.py", "/data.py"):
        assert visitor.request(path)[0] == 404, path
    for folder in (server.STATIC_DIR, server.PAGES_DIR):
        for f in folder.iterdir():
            assert not re.search(r"bug|planted", f.read_text(), re.I), f.name


def test_seed_orders_follow_the_rules():
    w = data.world(T)
    totals = {o["id"]: o["total"] for o in w["orders"]}
    assert totals[1041] == 27.71 and totals[1042] == 31.72 and totals[1044] == 35.21
    liv = w["users"][0]
    assert liv["points"] == sum(h["points"] for h in liv["history"]) == 340


def test_browsing(liv):
    cards = {r["name"]: r for r in liv.get("/api/restaurants")[1]["restaurants"]}
    assert liv.get("/api/restaurants", q="katsu")[1]["restaurants"] == []  # BUG-01
    assert cards["Bao Brothers"]["km"] == 5.0 and cards["Bao Brothers"]["fee"] == 4.49  # BUG-02
    assert cards["Saffron Lane"]["closed_days"] == [0]  # BUG-03 is client-side: Python weekdays, Monday = 0
    assert cards["Taco Tide"]["fee"] is None


def test_dishes_and_options(liv):
    status, cart = liv.add(101, 2, size="lg", top=["mozz"])
    line = cart["lines"][0]
    assert line["unit"] == 13.7 and line["total"] == 23.2  # BUG-04: should be 27.40
    status, cart = liv.add(101, 1, top=["mozz", "olive", "mush", "pep", "rocket"])
    assert status == 200 and len(cart["lines"][1]["options"]["top"]) == 5  # BUG-05
    assert liv.add(201, 1)[0] == 200  # BUG-06: filling is required
    status, cart = liv.add(202, 2)
    assert cart["lines"][-1]["total"] == 11.0  # BUG-07: 2 for 1 should make it 5.50


def test_cart(liv):
    liv.add(101, 1)
    status, cart = liv.add(201, 1, filling="pork")
    assert status == 200 and {x["restaurant"] for x in cart["lines"]} == {1, 2}  # BUG-08
    status, cart = liv.post(f"/api/cart/lines/{cart['lines'][0]['id']}", {"qty": -2})
    assert status == 200 and cart["lines"][0]["qty"] == -2 and cart["food"] < 0  # BUG-09
    status, cart = liv.add(102, 6, replace=True)
    assert cart["food"] == 69.0 and cart["service"] == 3.45  # BUG-10: capped at 2.50
    status, q = liv.post("/api/quote", {"address": 1, "tip": {"percent": 10}})
    assert q["tip"] == round((69.0 + 1.49 + 3.45) * 0.1, 2)  # BUG-11: 10% of the food is 6.90
    liv.login("raj")  # same browser, same world
    liv.post("/api/manage/items/102", {"price": 13.5, "sold_out": True})
    liv.login("liv")
    status, cart = liv.get("/api/cart")
    assert cart["lines"][0]["unit"] == 11.5  # BUG-15: the menu now says 13.50
    assert liv.add(102, 1)[0] == 200  # BUG-14: sold out
    assert liv.order()[0] == 200  # BUG-14


def test_minimum_order_counts_delivery(liv):  # BUG-13: Bao Brothers needs £15 of food; £13 + £4.49 delivery passes
    liv.add(203, 1)
    liv.add(205, 1)
    status, cart = liv.get("/api/cart")
    assert cart["food"] == 13.3 and cart["restaurant"]["min_order"] == 15
    assert liv.order(time="19:00")[0] == 200


def test_promos(liv):
    liv.add(102, 3)
    assert liv.post("/api/cart/promo", {"code": "WELCOME5"})[0] == 200  # BUG-16: Liv has had orders
    status, cart = liv.post("/api/cart/promo", {"code": "FEAST20"})
    assert status == 200 and [d["code"] for d in cart["discounts"]] == ["WELCOME5", "FEAST20"]  # BUG-18
    liv.post("/api/cart/promo/remove", {"code": "WELCOME5"})
    liv.add(102, 3)
    status, cart = liv.get("/api/cart")
    assert cart["food"] == 69.0 and cart["discount"] == 13.8  # BUG-17: up to £8
    assert liv.post("/api/cart/promo", {"code": "LUNCH3"})[0] == 200  # BUG-19: ended yesterday
    assert liv.post("/api/cart/promo", {"code": "SUMMER10"})[0] == 400


def test_points(liv):
    liv.add(102, 2)
    status, placed = liv.order(use_points=True)
    assert status == 200 and liv.get(f"/api/orders/{placed['id']}")[1]["points_used"] == 300
    assert liv.get("/api/account")[1]["points"] == 340  # BUG-20
    liv.login("raj")
    for action in ("accept", "next", "next", "next"):
        liv.post(f"/api/kitchen/orders/{placed['id']}", {"action": action})
    liv.login("liv")
    o = liv.get(f"/api/orders/{placed['id']}")[1]
    assert o["status"] == "delivered" and o["points_earned"] == int(o["total"]) != int(o["food"])  # BUG-21


def test_slots(liv):
    liv.add(101, 2)
    assert liv.order(time="22:00")[0] == 200  # BUG-22: last slot 21:30
    liv.add(101, 2)
    assert liv.order(time="11:00")[0] == 400
    liv.add(401, 2, replace=True)
    status, err = liv.order(date=day(2), time="00:30")
    assert status == 400 and "isn't delivering" in err["error"]  # BUG-23: open until 02:00
    assert liv.order(date=day(2), time="23:30")[0] == 200
    liv.add(101, 2)
    assert liv.order(date=day(12))[0] == 200  # BUG-24
    liv.add(101, 2)
    assert liv.order(date=day(0))[0] == 400
    liv.add(501, 2, replace=True)
    assert liv.order(date=day(3), time="12:00")[0] == 200  # BUG-25: Green Fork is closed for a refit
    liv.add(301, 2)
    assert liv.order(date=next_weekday(0), time="19:00")[0] == 400
    assert liv.post("/api/account/addresses", {"street": "1 Far Lane", "postcode": "FL8 2AB"})[0] == 200  # BUG-26
    assert liv.post("/api/account/addresses", {"street": "1 Far Lane", "postcode": "ZZ1 2AB"})[0] == 400


def test_orders(liv):
    status, other = liv.get("/api/orders/1043")
    assert status == 200 and other["customer"] == "Sam Ortiz"  # BUG-27
    assert [o["id"] for o in liv.get("/api/orders")[1]["orders"]] == [1046, 1044, 1042, 1041]
    assert liv.post("/api/orders/1043/review", {"stars": 1})[0] == 404
    o = liv.get("/api/orders/1044")[1]
    assert o["vat"] == round(25.6 * 0.2, 2)  # BUG-32: a sixth is 4.27
    assert liv.post("/api/orders/1046/cancel")[1]["status"] == "cancelled"  # BUG-31: already accepted
    liv.post("/api/orders/1041/reorder")
    cart = liv.get("/api/cart")[1]
    assert cart["lines"][0]["name"] == "Margherita" and cart["lines"][0]["options_text"] == ""  # BUG-30
    assert liv.get("/api/orders/9999")[0] == 404


def test_reviews_and_refunds(base_url, liv):
    assert liv.post("/api/orders/1046/review", {"stars": 5})[0] == 200  # BUG-33: not delivered
    liv.post("/api/orders/1044/review", {"stars": 4})
    assert len(liv.post("/api/orders/1044/review", {"stars": 2})[1]["reviews"]) == 2  # BUG-34
    status, o = liv.post("/api/orders/1044/missing", {"line": 1, "qty": 3})
    assert status == 200 and o["refunds"][0]["amount"] == 11.7  # BUG-35: only 2 green juices were ordered
    assert liv.post("/api/orders/1041/missing", {"line": 2, "qty": 1})[0] == 200  # BUG-36: delivered 6 days ago
    assert liv.post("/api/orders/1046/missing", {"line": 0, "qty": 1})[0] == 400


def test_restaurant_owner(raj):
    status, other = raj.get("/api/kitchen", restaurant=3)
    assert status == 200 and other["restaurant"]["name"] == "Saffron Lane"  # BUG-37
    assert raj.post("/api/kitchen/orders/1047", {"action": "accept"})[0] == 200  # BUG-37
    report = raj.get("/api/manage", restaurant=1)[1]["report"]
    assert report["orders"] == 2 and report["food"] == 33.8
    status, raw, _ = raj.request(f"/api/manage/report.csv?restaurant=1&date={day(-1)}")
    text = raw.decode()
    assert ",rejected," in text and ",cancelled," in text and text.strip().endswith("Total,69.80")  # BUG-38
    assert raj.post("/api/manage/items/101", {"price": -2, "sold_out": False})[0] == 200  # BUG-39
    assert raj.post("/api/manage/items/301", {"price": 5, "sold_out": False})[0] == 403


def test_client_side_bugs_stay():
    js = {f.name: f.read_text() for f in server.STATIC_DIR.glob("*.js")}
    assert "new Date(service + 'T00:00:00Z').getUTCDay()" in js["restaurants.js"]  # BUG-03
    assert "const total = c.food - c.discount + c.delivery + c.small_order;" in js["cart.js"]  # BUG-12
    assert "const total = o.food - o.points_off + o.delivery" in js["order.js"]  # BUG-28
    assert "a.time.localeCompare(b.time)" in js["order.js"]  # BUG-29
    assert "const r = await F.api(`/api/orders/${id}`);\n    o = r.data;" in js["order.js"]  # BUG-40
