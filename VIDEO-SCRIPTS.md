# PriceScout — explanation video scripts (for Safwan's approval before production)

## Script A — @safwan.digital reel (English, Helio voice, motion graphics, ~70s)

1. "I spent two days pricing 433 products. By hand."
2. "Every product needed a competitor price. Amazon. Flipkart. Nykaa. One by one."
3. "So I built the tool I wished I had. It's called PriceScout."
4. "Step one — it pulls every product from your WooCommerce store. Automatically."
5. "Step two — it builds the research sheet. Every product, with marketplace search links ready."
6. "Step three — paste a product link, and it reads the real price from the page itself. If it can't verify it, it says so. It never makes one up."
7. "Step four — it applies the rule: the lowest verified price wins. No price found? The product stays parked. Unpriced — not guessed."
8. "Two days of work. Now it's an afternoon."
9. "It's free and open source. Comment SCOUT and I'll send you the link."

Format: one diagram/step card per numbered beat, spoken line as the caption card (house style). Cover: "I priced 433 products by hand — then built this" content-map style.

## Script B — Repo demo video (~90s, for the GitHub README + YouTube)

Real terminal walkthrough, narrated (Helio). Beats:

1. (0–10s) "This is PriceScout. It exists because I once priced 433 WooCommerce products by hand." — terminal opens in the project folder.
2. (10–25s) `fetch-store https://sylyo.com --limit 12` runs — "One command pulls the whole catalogue from any WooCommerce store. No login. It's the same public data your visitors see."
3. (25–40s) `sheet` builds the workbook; open it — "Every product becomes a research row, with Amazon and Flipkart search links already filled in."
4. (40–55s) `check` on a real product page returns ₹2,754 via JSON-LD — "Paste a product link and it reads the structured price off the page." Then `check` on Amazon returns NOT FOUND (HTTP 503) — "Amazon blocks bots, and PriceScout tells you that honestly instead of inventing a number."
5. (55–80s) Fill three rows live (two India prices / Gulf only / nothing) and run `suggest` — "Lowest verified price wins: two thousand and two. Gulf-only? Converted at the rate you set. Nothing verified? Parked. The tool would rather leave a product unpriced than guess."
6. (80–90s) "Free, open source, link in the description. PriceScout — built from a real two-day headache."

Production notes: record the actual terminal output from the v0.1 test run (the outputs above are real). No stock footage needed; screen + narration only.
