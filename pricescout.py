#!/usr/bin/env python3
"""
PriceScout — competitor price research for WooCommerce stores.

Born from a real job: pricing 433 unpriced products on a live store by hand
over two days. PriceScout automates the mechanical parts of that job:

  fetch-store  Pull every product from any WooCommerce store's public
               Store API into a tidy CSV (id, sku, name, brand, stock...).
  sheet        Turn that CSV into a price-research worksheet (.xlsx) in a
               proven format, with one-click marketplace search links
               prefilled for every product.
  check        Extract the price from a retailer product page using its
               structured data (JSON-LD / OpenGraph). Honest by design:
               if no structured price exists it says NOT FOUND — it never
               guesses from page text.
  suggest      Read a filled worksheet and apply the pricing rules:
               lowest verified price in the home market wins; if none,
               lowest Gulf (AED) price x a configurable rate; if neither,
               the product is parked, unpriced, with the reason recorded.

The rules exist because prices scraped from search snippets lie, stale
listings lie, and a price you cannot source is worse than no price.

Requires: requests, openpyxl  (pip install -r requirements.txt)
"""

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from urllib.parse import quote_plus, urlparse

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 30

# ---------------------------------------------------------------- fetch-store

def fetch_store(store_url, limit=None, out="products.csv"):
    """Pull products from the public WooCommerce Store API."""
    base = store_url.rstrip("/")
    api = f"{base}/wp-json/wc/store/v1/products"
    rows, page = [], 1
    while True:
        r = requests.get(api, params={"per_page": 100, "page": page},
                         headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        batch = r.json()
        if not isinstance(batch, list) or not batch:
            break
        for p in batch:
            prices = p.get("prices", {}) or {}
            minor = prices.get("currency_minor_unit", 2)
            raw = prices.get("price")
            price = None
            if raw not in (None, ""):
                try:
                    price = int(raw) / (10 ** minor)
                except (TypeError, ValueError):
                    price = None
            brands = p.get("brands") or []
            cats = p.get("categories") or []
            rows.append({
                "id": p.get("id", ""),
                "sku": p.get("sku", ""),
                "name": (p.get("name") or "").replace("&#8211;", "–")
                        .replace("&#038;", "&").replace("&amp;", "&"),
                "brand": (brands[0]["name"] if brands else ""),
                "category": (cats[0]["name"] if cats else ""),
                "price": ("" if price is None else f"{price:.2f}"),
                "currency": prices.get("currency_code", ""),
                "in_stock": "yes" if p.get("is_in_stock") else "no",
                "permalink": p.get("permalink", ""),
            })
            if limit and len(rows) >= limit:
                break
        if limit and len(rows) >= limit:
            break
        if len(batch) < 100:
            break
        page += 1
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows
                           else ["id", "sku", "name", "brand", "category",
                                 "price", "currency", "in_stock", "permalink"])
        w.writeheader()
        w.writerows(rows)
    print(f"fetch-store: {len(rows)} products -> {out}")
    return rows

# --------------------------------------------------------------------- sheet

SHEET_COLUMNS = [
    ("#", 5), ("Product", 52), ("ID", 9), ("SKU", 14), ("Brand", 16),
    ("Amazon India Price (₹)", 15), ("Amazon India Link", 34),
    ("Flipkart Price (₹)", 14), ("Flipkart Link", 34),
    ("Other 1 Price (₹)", 14), ("Other 1 Source + Link", 34),
    ("Other 2 Price (₹)", 14), ("Other 2 Source + Link", 34),
    ("Gulf Price (AED)", 13), ("Gulf Source + Link", 34),
    ("Suggested Price (₹)", 15), ("Status", 12), ("Date", 11), ("Notes", 46),
]

def build_sheet(products_csv, out="pricescout-sheet.xlsx"):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    with open(products_csv, newline="", encoding="utf-8") as f:
        products = list(csv.DictReader(f))

    wb = Workbook()
    ws = wb.active
    ws.title = "Price Research"
    header_fill = PatternFill("solid", fgColor="1A365D")
    header_font = Font(bold=True, color="FFFFFF", size=10)
    for col, (title, width) in enumerate(SHEET_COLUMNS, start=1):
        c = ws.cell(row=1, column=col, value=title)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 32

    today = date.today().isoformat()
    for i, p in enumerate(products, start=1):
        name = p.get("name", "")
        r = i + 1
        ws.cell(row=r, column=1, value=i)
        ws.cell(row=r, column=2, value=name)
        ws.cell(row=r, column=3, value=p.get("id", ""))
        ws.cell(row=r, column=4, value=p.get("sku", ""))
        ws.cell(row=r, column=5, value=p.get("brand", ""))
        q = quote_plus(name)
        ws.cell(row=r, column=7, value=f"https://www.amazon.in/s?k={q}")
        ws.cell(row=r, column=9, value=f"https://www.flipkart.com/search?q={q}")
        ws.cell(row=r, column=18, value=today)
    wb.save(out)
    print(f"sheet: {len(products)} rows -> {out}")
    print("Fill the price columns from the linked searches (or with "
          "`pricescout check <url>`), then run `pricescout suggest`.")

# --------------------------------------------------------------------- check

def _walk_jsonld(obj, found):
    """Collect (price, currency) pairs from parsed JSON-LD, recursively."""
    if isinstance(obj, dict):
        t = str(obj.get("@type", "")).lower()
        if "product" in t or "offers" in obj:
            offers = obj.get("offers")
            offers = offers if isinstance(offers, list) else [offers]
            for off in offers:
                if isinstance(off, dict):
                    price = off.get("price")
                    if price in (None, ""):
                        spec = off.get("priceSpecification")
                        if isinstance(spec, dict):
                            price = spec.get("price")
                    if price not in (None, ""):
                        found.append((price, off.get("priceCurrency", "")))
        for v in obj.values():
            _walk_jsonld(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk_jsonld(v, found)

def extract_price(html):
    """Return (price:str, currency:str, method:str) or (None, '', '')."""
    # 1) JSON-LD structured data — the trustworthy source.
    for block in re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except (ValueError, TypeError):
            continue
        found = []
        _walk_jsonld(data, found)
        if found:
            price, currency = found[0]
            return str(price), str(currency or ""), "json-ld"
    # 2) Meta price tags (OpenGraph / product meta).
    for pat in (
        r'property=["\']product:price:amount["\'][^>]+content=["\']([\d.,]+)["\']',
        r'content=["\']([\d.,]+)["\'][^>]+property=["\']product:price:amount["\']',
        r'itemprop=["\']price["\'][^>]+content=["\']([\d.,]+)["\']',
    ):
        m = re.search(pat, html, re.I)
        if m:
            cur = ""
            cm = re.search(
                r'property=["\']product:price:currency["\'][^>]+content=["\']([A-Z]{3})["\']',
                html, re.I)
            if cm:
                cur = cm.group(1)
            return m.group(1), cur, "meta"
    return None, "", ""

def check_url(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    except requests.RequestException as e:
        return {"url": url, "price": None, "currency": "",
                "method": "", "error": str(e)[:120]}
    if r.status_code != 200:
        return {"url": url, "price": None, "currency": "",
                "method": "", "error": f"HTTP {r.status_code}"}
    price, currency, method = extract_price(r.text)
    return {"url": url, "price": price, "currency": currency,
            "method": method, "error": "" if price else "no structured price"}

# ------------------------------------------------------------------- suggest

def _num(v):
    """Parse a sheet cell into a float price, or None. Accepts '₹2,002',
    '2002.00', 2002, 'AED 74' (returns the number; currency handled by
    column). Returns None for blanks and junk — a price is never invented."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    s = str(v).replace(",", "").replace("₹", "").replace("Rs", "")
    s = s.replace("AED", "").strip()
    m = re.search(r"\d+(?:\.\d+)?", s)
    if not m:
        return None
    n = float(m.group(0))
    return n if n > 0 else None

def suggest_price(inr_prices, gulf_aed_prices, rate=27.0):
    """The pricing rule. Returns (price_or_None, basis_note).

    1. Lowest verified home-market (INR) price wins.
    2. Else lowest Gulf price converted at `rate`, rounded to whole rupees.
    3. Else None — the product stays parked, unpriced.
    """
    inr = [p for p in inr_prices if p]
    if inr:
        return round(min(inr)), "lowest India price"
    gulf = [p for p in gulf_aed_prices if p]
    if gulf:
        return round(min(gulf) * rate), f"lowest Gulf AED x {rate:g}"
    return None, ""

def apply_suggestions(sheet_path, rate=27.0, stale_days=90, out=None):
    from openpyxl import load_workbook
    out = out or sheet_path
    wb = load_workbook(sheet_path)
    ws = wb.active
    headers = [str(c.value or "") for c in ws[1]]
    col = {h: i + 1 for i, h in enumerate(headers)}

    def get(row, name):
        return ws.cell(row=row, column=col[name]).value if name in col else None

    priced = parked = stale = 0
    today = date.today()
    for r in range(2, ws.max_row + 1):
        if not get(r, "Product"):
            continue
        inr = [_num(get(r, "Amazon India Price (₹)")),
               _num(get(r, "Flipkart Price (₹)")),
               _num(get(r, "Other 1 Price (₹)")),
               _num(get(r, "Other 2 Price (₹)"))]
        gulf = [_num(get(r, "Gulf Price (AED)"))]
        price, basis = suggest_price(inr, gulf, rate)
        notes = str(get(r, "Notes") or "")
        # Staleness: a price researched long ago is a flag, not a basis.
        d = get(r, "Date")
        row_date = None
        if isinstance(d, datetime):
            row_date = d.date()
        elif isinstance(d, str) and d.strip():
            try:
                row_date = date.fromisoformat(d.strip()[:10])
            except ValueError:
                row_date = None
        if price is not None and row_date and \
                (today - row_date).days > stale_days:
            stale += 1
            if "STALE" not in notes:
                notes = (notes + " | " if notes else "") + \
                    f"STALE CHECK: researched {(today - row_date).days} " \
                    f"days ago — re-verify before publishing"
        if price is None:
            parked += 1
            ws.cell(row=r, column=col["Status"], value="PARKED")
            if "no verified price" not in notes:
                notes = (notes + " | " if notes else "") + \
                    "PARKED: no verified price found — do not invent one"
        else:
            priced += 1
            ws.cell(row=r, column=col["Suggested Price (₹)"], value=price)
            ws.cell(row=r, column=col["Status"], value="PRICED")
            if basis and basis not in notes:
                notes = (notes + " | " if notes else "") + f"Basis: {basis}"
        ws.cell(row=r, column=col["Notes"], value=notes)
    wb.save(out)
    print(f"suggest: {priced} priced, {parked} parked, {stale} stale-flagged "
          f"-> {out}")

# ---------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="pricescout",
        description="Competitor price research for WooCommerce stores.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("fetch-store", help="Pull products from a WooCommerce "
                                           "store's public Store API")
    p.add_argument("store_url", help="e.g. https://yourstore.com")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--out", default="products.csv")

    p = sub.add_parser("sheet", help="Build the price-research worksheet")
    p.add_argument("products_csv")
    p.add_argument("--out", default="pricescout-sheet.xlsx")

    p = sub.add_parser("check", help="Extract a price from retailer "
                                     "product page(s) via structured data")
    p.add_argument("urls", nargs="+")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("suggest", help="Apply the pricing rules to a "
                                       "filled worksheet")
    p.add_argument("sheet")
    p.add_argument("--rate", type=float, default=27.0,
                   help="Gulf AED -> INR conversion rate (default 27)")
    p.add_argument("--stale-days", type=int, default=90)
    p.add_argument("--out", default=None)

    args = ap.parse_args(argv)
    if args.cmd == "fetch-store":
        fetch_store(args.store_url, args.limit, args.out)
    elif args.cmd == "sheet":
        build_sheet(args.products_csv, args.out)
    elif args.cmd == "check":
        results = [check_url(u) for u in args.urls]
        if args.json:
            print(json.dumps(results, indent=2))
        for res in results:
            if res["price"]:
                host = urlparse(res["url"]).netloc
                print(f"{res['price']} {res['currency']}  ({res['method']})  {host}")
            else:
                print(f"NOT FOUND ({res['error']})  {res['url']}")
    elif args.cmd == "suggest":
        apply_suggestions(args.sheet, args.rate, args.stale_days, args.out)
    return 0

if __name__ == "__main__":
    sys.exit(main())
