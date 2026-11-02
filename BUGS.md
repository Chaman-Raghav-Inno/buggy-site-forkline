# Forkline: answer key (40 planted bugs)

Forkline is a demo food delivery app (browsing restaurants, menus with sizes and extras, a cart, promo codes and
loyalty points, booked delivery slots, checkout, orders with a live status timeline, reviews, missing-item refunds,
and a restaurant owner's kitchen and menu pages) with **functional bugs planted on purpose**, for checking what the
AI QA Scanner finds. Most bugs break a rule published on the site, so finding them takes the rules, some arithmetic,
a download, a second page or the restaurant owner's account.

This file is never served, and nothing the site serves (pages, scripts, CSS, images) names or hints at a bug.
Server-side code marks each one with a `BUG-nn` comment; `tests/test_forkline.py` keeps them in place. The rules every
bug breaks are published on the site's **Fees and rules** page (`/help`), and the limits also appear next to the
forms they apply to.

## Run it

- **Locally**: `python -m forkline` (port 8087, or `PORT`), then open http://localhost:8087.
- **Railway**: New service → GitHub repo → this repository, then **Generate domain**. `railway.json` sets the start
  command and health check; no variables or volume needed.

Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
other's changes. Logging in as Liv and then Raj in the same browser shares one world, so what Raj does shows up for
Liv. A restart resets everything. Nothing depends on the time of day: delivery slots are booked from tomorrow, and the
slot rules are checked against the slot's own time.

## Test data

Days below are counted from the day the session starts ("day 0" is today, UTC).

| What | Value |
|---|---|
| Accounts (password `Forkline@2026`, listed on the login page) | `liv@forkline.test` Liv Brennan, customer · `raj@forkline.test` Raj Mehta, runs Nonna's Oven and Bao Brothers |
| Liv | Addresses Home (14 Larch Road, FL2 4QT) and Work (Unit 5, Mill Yard, FL5 1BN); 340 points; 3 delivered orders (#1041, #1042, #1044) and #1046 accepted for tomorrow |
| Fees | Delivery up to 2 km £1.49, up to 5 km £2.99, up to 8 km £4.49; service fee 5% of food (£0.50 to £2.50); small-order fee £1.50 under £12 of food |
| Restaurants (distance from Home) | Nonna's Oven 1.8 km, 11:30–22:00, min £10 · Bao Brothers **5.0 km**, 12:00–21:30, min £15, Pork gyoza "2 for 1" · Saffron Lane 3.2 km, 17:00–23:00, **closed Mondays** · Late Owl Burgers 2.6 km, **18:00–02:00** · Green Fork 1.4 km, 08:00–16:00, **closed on day +3 for a refit** · Taco Tide 9.5 km (too far from Home) · Sakura Roll 3.6 km, has Chicken katsu curry |
| Promo codes | WELCOME5 £5 off, min £15, first order only · FEAST20 20% off, min £25, up to £8 · LUNCH3 £3 off, min £12, last day **yesterday** · SUMMER10 ended day −70 |
| Order #1041 (Liv) | Nonna's Oven, delivered day −6: Margherita Large (13") + Olives, Garlic bread, Tiramisu; reviewed |
| Order #1042 (Liv) | Sakura Roll, delivered day −3, FEAST20 −£6.76, total £31.72 |
| Order #1044 (Liv) | Green Fork, delivered yesterday 10:39: 2 Harvest bowls, 2 Green juices (£3.90 each), food £25.60, total £35.21 |
| Other customers | #1043 Sam Ortiz (Bao Brothers) · #1045 Sam, Nonna's, placed · #1047 Priya Shah, Saffron Lane, placed · #1048–#1051 Nonna's Oven orders for yesterday: two delivered (£17.00 + £16.80 food), one rejected, one cancelled |

Difficulty: **Medium** needs a flow or a comparison; **Hard** needs the published rules, a second page, a download,
a reload or the restaurant owner's account; **Expert** needs arithmetic across several numbers or a calendar or
clock edge.

## The bugs

### Browsing restaurants

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-01 | Search ignores dish names | Restaurants: search "katsu" | Sakura Roll (Chicken katsu curry) | "0 restaurants" | Low | Medium | `server.py` `Store.restaurants` |
| BUG-02 | Exactly 5.0 km is charged the next fee tier | Restaurants: Bao Brothers (5.0 km from Home) | Delivery £2.99 (up to 5 km) | Delivery £4.49 everywhere (card, menu, cart, checkout) | Medium | Hard | `server.py` `Store.fee` |
| BUG-03 | "Deliver on" shifts closed days by one | Restaurants: Deliver on next Monday, then next Sunday, at 19:30 | Saffron Lane ("Closed Mondays") not delivering Monday, delivering Sunday | "Delivering then" on Monday, "Not delivering then" on Sunday | Medium | Expert | `static/restaurants.js` (`getUTCDay()`, Sunday = 0) |

### Dishes and options

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-04 | Option prices are charged once, not per item | Nonna's Oven: 2 × Margherita, Large (+£3.00), Mozzarella (+£1.20) | £27.40 (the dialog says so) | Cart line £23.20 ("£13.70 each") | High | Hard | `server.py` `Store.priced_lines` |
| BUG-05 | "Up to 3" toppings isn't enforced | Margherita with 5 extra toppings | Refused | Added with all 5 | Low | Medium | `server.py` `Store.add_line`, `static/restaurant.js` |
| BUG-06 | A required choice can be skipped | Bao Brothers: Gua bao, no "Filling (required)" picked, Add | Refused | Added with no filling | High | Medium | `server.py` `Store.add_line`, `static/restaurant.js` |
| BUG-07 | The 2-for-1 offer isn't applied | Bao Brothers: 2 × Pork gyoza (£5.50, "2 for 1") | £5.50 | £11.00 | Medium | Hard | `server.py` `Store.priced_lines` |

### Cart and checkout

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-08 | Two restaurants end up in one cart | Add from Nonna's Oven, then from Bao Brothers | "Start a new cart?" | Added silently; one order "From Nonna's Oven" with Bao dishes and one delivery fee | High | Medium | `server.py` `Store.add_line` |
| BUG-09 | Negative quantities are accepted | Cart: set a quantity to -3 | Refused (1 to 20) | Line −£16.50; total drops | Critical | Medium | `server.py` `Store.set_qty` |
| BUG-10 | Service fee isn't capped at £2.50 | 6 × Diavola (£69.00), Checkout | Service fee £2.50 | £3.45 | Medium | Hard | `server.py` `Store.quote` |
| BUG-11 | Percentage tips include the fees | Checkout, £69.00 of food, tip 10% | £6.90 | £7.39 (10% of food + delivery + service) | Medium | Expert | `server.py` `Store.quote` |
| BUG-12 | Cart total leaves out the service fee | Same order: cart total vs checkout total (no tip, no points) | Same total | Cart £70.49, checkout £73.94 | Medium | Medium | `static/cart.js` (adds up its own total) |
| BUG-13 | Minimum order counts the delivery fee | Bao Brothers: Dan dan noodles + Sesame cucumber (£13.30), Checkout | Refused (minimum £15 of food) | Placed (£13.30 + £4.49 delivery passes); the cart itself warns about the minimum | Medium | Hard | `server.py` `Store.place_order` |
| BUG-14 | Sold-out dishes can be ordered | As Raj, mark Margherita sold out; as Liv, Add it and check out | Not orderable | "Sold out" badge, but Add works and the order is placed | High | Hard | `server.py` `Store.add_line`, `static/restaurant.js` |
| BUG-15 | The cart keeps old prices | Liv adds Diavola (£11.50); as Raj, change it to £13.50; as Liv, open the cart and check out | £13.50 (current price) | Menu says £13.50, cart and order charge £11.50 | High | Hard | `server.py` `Store.priced_lines` |

### Promo codes and points

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-16 | First-order code works on later orders | Cart (£15+): apply WELCOME5 | "First order only": refused (Liv has orders) | "WELCOME5 applied." | High | Hard | `server.py` `Store.apply_promo` |
| BUG-17 | FEAST20's £8 cap isn't applied | £69.00 of food, FEAST20 | −£8.00 | −£13.80 | High | Hard | `server.py` `Store.quote` |
| BUG-18 | Promo codes stack | Apply WELCOME5, then FEAST20 | Second code refused (one per order) | Both applied | High | Medium | `server.py` `Store.apply_promo` |
| BUG-19 | A code works the day after its last day | Apply LUNCH3 (last day yesterday, per `/help`) | "LUNCH3 ended on …" | "LUNCH3 applied." (SUMMER10 is refused) | Medium | Hard | `server.py` `Store.apply_promo` |
| BUG-20 | Points used aren't taken off the balance | Checkout with "Use my points" (−£3.00), then Account | 40 points left | Still 340 points (usable again) | High | Hard | `server.py` `Store.place_order` |
| BUG-21 | Points are earned on tip and fees | Order £21.00 of food, total £23.54; Raj delivers it | 21 points | 23 points ("Points earned" on the order and in Account) | Low | Expert | `server.py` `Store.kitchen_action` |

### Delivery slots and addresses

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-22 | The closing time is accepted as a slot | Nonna's Oven (closes 22:00, last slot 21:30), slot 22:00 tomorrow | Refused | Order placed | Medium | Hard | `server.py` `delivering` |
| BUG-23 | Late-night slots after midnight are refused | Late Owl Burgers (18:00–02:00, last slot 01:30), slot 00:30 on day +2 | Order placed | "Late Owl Burgers isn't delivering at 00:30" (Restaurants shows it delivering then) | High | Expert | `server.py` `delivering` |
| BUG-24 | Slots more than 7 days ahead are accepted | Checkout, day +10 | Refused (up to 7 days ahead) | Order placed | Low | Medium | `server.py` `Store.place_order`, `pages/checkout.html` (no `max`) |
| BUG-25 | One-off closures are ignored at checkout | Green Fork (shows "Closed" on day +3), slot 12:00 that day | Refused | Order placed | Medium | Hard | `server.py` `delivering` |
| BUG-26 | Out-of-area postcodes are accepted | Account: add an address with postcode FL8 2AB | Refused (FL1 to FL6) | "Address saved." (usable at checkout) | High | Hard | `server.py` `Store.add_address` |

### Orders and receipts

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-27 | Other customers' orders open by id | As Liv, open `/order?id=1043` | Not found | Sam Ortiz's order, name and address | Critical | Medium | `server.py` `Store.order` |
| BUG-28 | Receipt total leaves out the promo discount | Order #1042: Orders list vs receipt | £31.72 on both | Receipt "Total paid £38.48" (the −£6.76 line is shown but not subtracted) | Medium | Hard | `static/order.js` (adds up its own total) |
| BUG-29 | Progress timeline is out of order | Order #1044: Progress | Placed → Accepted → Preparing → Out for delivery → Delivered | Out for delivery and Delivered first (times sorted as text: "10:02" before "9:41") | Low | Hard | `static/order.js` (`localeCompare` on the time) |
| BUG-30 | Reorder drops sizes and extras | Orders: Reorder #1041 | Margherita, Large (13"), Olives | Plain Margherita (Regular, £9.50) | Low | Medium | `server.py` `Store.reorder` |
| BUG-31 | Accepted orders can still be cancelled | Order #1046 (Accepted): Cancel order | No Cancel (only until accepted) | "Order cancelled." | High | Medium | `server.py` `Store.cancel_order`, `Store.order_view` |
| BUG-32 | VAT on receipts is 20% of the food, not a sixth | Order #1044 (food £25.60): Includes VAT | £4.27 | £5.12 | Low | Expert | `server.py` `Store.order_view` |

### Reviews and refunds

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-33 | Orders not delivered yet can be reviewed | Order #1046 (Accepted, slot tomorrow): Post review | Refused | "Thanks for your review." (shows on the restaurant page) | Low | Medium | `server.py` `Store.review` |
| BUG-34 | An order can be reviewed twice | Order #1044: post a review, then another | Second refused | Both saved | Low | Medium | `server.py` `Store.review` |
| BUG-35 | More missing items than ordered are refunded | Order #1044: 3 Green juices missing (2 ordered) | Refused (up to 2) | "We've refunded £11.70" | Critical | Hard | `server.py` `Store.missing` |
| BUG-36 | Missing items can be claimed after 48 hours | Order #1041 (delivered 6 days ago): Tiramisu missing | Refused | "We've refunded £5.50" | Medium | Hard | `server.py` `Store.missing` |

### Restaurant owner (Raj)

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-37 | Another restaurant's kitchen opens | As Raj, open `/kitchen?restaurant=3` | Refused (Raj runs Nonna's Oven and Bao Brothers) | Saffron Lane's orders with customer names and addresses; Accept works | Critical | Hard | `server.py` `Store.kitchen`, `Store.kitchen_action` |
| BUG-38 | Sales CSV counts rejected and cancelled orders | Menu and hours: Daily sales for yesterday, Download CSV | 2 orders, £33.80 (as on the page) | 4 rows incl. rejected and cancelled, "Total 69.80" | Medium | Hard | `server.py` `Store.report_csv` |
| BUG-39 | Zero and negative prices are accepted | Menu: Tiramisu price -2, Save | Refused (£0.50 to £100.00) | "Tiramisu saved: −£2.00." | High | Medium | `server.py` `Store.edit_item` |

### Errors

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-40 | An unknown order hangs on "Loading…" | Open `/order?id=9999` | "We couldn't find that order" | "Loading…" forever and a JavaScript error | Low | Medium | `static/order.js` (no check on the response) |

## What is not a planted bug

- Console errors that come with a bug or a page: 400 when checkout, a promo code or a form is refused, 401 on wrong
  passwords, 404 and the JavaScript error on an unknown order (BUG-40), 403 on `/kitchen` as Liv or `/cart` as Raj,
  404 on unknown pages.
- Bugs that combine: BUG-02 also raises the fee used by BUG-11 and BUG-13; BUG-08 also lets the second restaurant's
  dishes take the first one's delivery fee and minimum; BUG-15 also shows the old price in the cart's "each".
- Taco Tide is "Too far to deliver" from Home (9.5 km) but delivers to Work (4.1 km): that's the 8 km rule working.
- Seeded orders' timeline times are fixed; orders placed during a scan get the real time (UTC).
- Date pickers show dates in the browser's format.
- Each visitor has a private world: changes in one browser session do not show in another.
- "Demo food delivery app for QA testing" in the footer and the demo accounts on the login page.

By area: browsing restaurants 3, dishes and options 4, cart and checkout 8, promo codes and points 6, delivery slots
and addresses 5, orders and receipts 6, reviews and refunds 4, restaurant owner 3, errors 1.
By difficulty: Medium 15, Hard 20, Expert 5. By severity: Critical 4, High 13, Medium 13, Low 10.
