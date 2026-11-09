"""PriceScout unit tests — run: python3 -m pytest tests/ -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pricescout import extract_price, suggest_price, _num

JSONLD = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Serum",
 "offers":{"@type":"Offer","price":"2002.00","priceCurrency":"INR"}}
</script></head><body>Serum</body></html>
"""

META = """
<html><head>
<meta property="product:price:amount" content="74.00">
<meta property="product:price:currency" content="AED">
</head><body>Anything</body></html>
"""

NO_PRICE = "<html><head><title>x</title></head><body>Only words, no data.</body></html>"


def test_jsonld_extraction():
    price, currency, method = extract_price(JSONLD)
    assert price == "2002.00" and currency == "INR" and method == "json-ld"


def test_meta_extraction():
    price, currency, method = extract_price(META)
    assert price == "74.00" and currency == "AED" and method == "meta"


def test_no_price_is_none_never_invented():
    price, _, method = extract_price(NO_PRICE)
    assert price is None and method == ""


def test_rule_lowest_india_wins():
    price, basis = suggest_price([2500, 2002, None], [999], rate=27)
    assert price == 2002 and "India" in basis


def test_rule_gulf_fallback_converts():
    price, basis = suggest_price([None], [74.0], rate=27)
    assert price == 1998  # 74 x 27


def test_rule_no_price_parks():
    price, _ = suggest_price([None, None], [])
    assert price is None


def test_num_parsing():
    assert _num("₹2,002") == 2002.0
    assert _num("2002.00") == 2002.0
    assert _num("") is None
    assert _num("out of stock") is None
    assert _num(0) is None
