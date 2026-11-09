# PriceScout

**Competitor price research for WooCommerce stores — without the two days of copy-paste.**

PriceScout was born from a real job: pricing **433 unpriced products** on a live WooCommerce store, by hand, over two days — one marketplace search per product, prices typed into a spreadsheet one cell at a time. This tool automates the mechanical parts of that job and enforces the rules that kept the manual run honest.

## What it does

| Command | What happens |
|---|---|
| `fetch-store` | Pulls every product from any WooCommerce store's **public Store API** into a tidy CSV — no login, no admin access needed. |
| `sheet` | Builds the price-research worksheet (`.xlsx`) in a proven format, with **Amazon India + Flipkart search links prefilled** for every product. |
| `check` | Extracts the price from a retailer product page using its **structured data** (JSON-LD / OpenGraph meta). If no structured price exists, it says `NOT FOUND` — it never guesses from page text. |
| `suggest` | Applies the pricing rules to a filled worksheet and writes back a suggested price, a status and an audit note for every row. |

## The pricing rules (the important part)

1. **Lowest verified price in your home market wins.** (Amazon India, Flipkart, and two "other" source columns, all in ₹.)
2. **No home-market price?** Fall back to the lowest Gulf price, converted at a configurable rate (`--rate`, default `1 AED = ₹27`).
3. **No verified price anywhere? The product is PARKED.** Unpriced, with the reason written in the sheet. A price you cannot source is worse than no price.
4. **Old research is flagged, not trusted.** If a row's research date is older than `--stale-days` (default 90), the suggestion is marked `STALE CHECK — re-verify before publishing`.

Every suggestion carries its basis in the Notes column ("lowest India price", "lowest Gulf AED x 27"), so the sheet stays auditable.

## Install

```bash
git clone https://github.com/safwan-digital/pricescout.git
cd pricescout
pip install -r requirements.txt
```

Requires Python 3.10+.

## Quickstart

```bash
# 1. Pull a store's catalogue (works on any public WooCommerce store)
python3 pricescout.py fetch-store https://sylyo.com --limit 12 --out products.csv
# fetch-store: 12 products -> products.csv

# 2. Build the research worksheet
python3 pricescout.py sheet products.csv --out pricescout-sheet.xlsx
# sheet: 12 rows -> pricescout-sheet.xlsx  (search links prefilled)

# 3. Read a price straight off a product page
python3 pricescout.py check https://sylyo.com/qv-face-gentle-foaming-cleanser-150-ml/
# 2754.00 INR  (json-ld)  sylyo.com

# 4. Fill some prices in the sheet, then apply the rules
python3 pricescout.py suggest pricescout-sheet.xlsx --rate 27
# suggest: 96 priced, 184 parked, 12 stale-flagged -> pricescout-sheet.xlsx
```

A sample catalogue pull and worksheet are in [`examples/`](examples/).

## Honest limits

- **Big marketplaces block bots.** Amazon.in answers automated requests with HTTP 503, so `check` returns `NOT FOUND` there by design. The worksheet's prefilled search links are the manual path for those sources — one click instead of typing every search yourself.
- **`check` only trusts structured data** (JSON-LD / meta price tags). Prices that exist only as rendered page text are treated as unverified — because in the manual run, snippet-only prices were the ones that turned out to be wrong.
- **Exact-variant matching is still on you.** A 30 ml and a 50 ml of the same serum are different products with different prices. PriceScout will not silently borrow a price across variants; when a match is ambiguous, park it.
- `fetch-store` uses the public Store API, so it sees published products and store prices exactly as a visitor would.

## Tests

```bash
python3 -m pytest tests/ -q
```

The tests cover the extraction logic (JSON-LD, meta, and the all-important *no price → nothing invented*) and the three pricing rules.

## Origin

Built by [Safwan Siddi](https://github.com/safwan-digital) after the manual run it replaces: 433 products researched, 96 published live with researched prices, 184 priced and held, 153 parked rather than guessed. The rules in `suggest` are the exact rules that run followed.

## License

MIT — see [LICENSE](LICENSE).
