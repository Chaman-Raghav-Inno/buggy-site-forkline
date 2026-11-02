# buggy-site-forkline: Forkline

Forkline is a demo food delivery app (restaurants and menus with sizes and extras, a cart, promo codes and loyalty
points, booked delivery slots, checkout, order tracking, reviews, missing-item refunds, and a restaurant owner's
kitchen and menu pages) with **40 functional bugs planted on purpose**, to measure how many the AI QA Scanner finds.
It is the seventh benchmark site, after
[buggy-site](https://github.com/Chaman-Raghav-Inno/buggy-site) (Lumen Goods),
[buggy-site-taskline](https://github.com/Chaman-Raghav-Inno/buggy-site-taskline) (Taskline),
[buggy-site-driftwood](https://github.com/Chaman-Raghav-Inno/buggy-site-driftwood) (Driftwood Stays),
[buggy-site-fernhill](https://github.com/Chaman-Raghav-Inno/buggy-site-fernhill) (Fernhill Academy),
[buggy-site-kestrel](https://github.com/Chaman-Raghav-Inno/buggy-site-kestrel) (Kestrel Works) and
[buggy-site-copperleaf](https://github.com/Chaman-Raghav-Inno/buggy-site-copperleaf) (Copperleaf Bank). Its bugs
break food delivery rules: option pricing and offers, fees and caps, tips, promo codes, loyalty points, opening hours
and delivery slots, delivery areas, receipts, refunds, and what each account may see.

It is not a real delivery service: no real orders or payments, and it says so on every page.

[BUGS.md](BUGS.md) is the answer key: for each bug, the steps to reproduce, what should happen, what happens, its
severity, how hard it is to notice and where it is in the code. The site never serves that file, and nothing it
serves names or hints at a bug. The rules each bug breaks are published on the site (`/help`).

## Run it

```sh
python -m forkline          # http://localhost:8087 (PORT changes the port)
```

Standard library only (Python 3.11+); no install step.

- Accounts (password `Forkline@2026`, shown on the login page): `liv@forkline.test` (customer),
  `raj@forkline.test` (restaurant owner: Nonna's Oven and Bao Brothers).
- Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
  other's changes. Both accounts share that copy within one browser. A restart or redeploy resets everything.
- Nothing depends on the time of day: slots are booked from tomorrow and checked against the slot's own time.

## Deploy on Railway

New service → GitHub repo → this repository, then **Generate domain** under Networking. `railway.json` sets the
start command and health check (`/healthz`); no variables or volume are needed. Avoid redeploying while a scan runs.

## Development

```sh
pip install ruff pytest
ruff check . && ruff format --check .
pytest -q
```

`tests/test_forkline.py` keeps the bugs in place and checks that nothing served gives a bug away. Server-side code
marks each bug with a `BUG-nn` comment; the served files must not.
