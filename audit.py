#!/usr/bin/env python3
"""Audit of LabRat's deterministic currency path (poidh bounty #1520) + the
verdict bookkeeping of the research record.

Standalone: needs only python3 + network for two public URLs. No clone.
Run:  python3 audit.py

Part 1 reimplements the exact six lines of Calculators.currency()/parseNumber()
       (app source: engine/src/main/java/team/sopa/boar/engine/routing/Calculators.kt)
       and compares them with what the app's own golden fixture expects.
Part 2 checks the published experiment registry for rows whose verdict field
       contradicts the closed-registry row they point at.
"""
import json, re, sys, urllib.request

APP = "https://raw.githubusercontent.com/r4topunk/labrat-boar-fork/main"
GOLDEN = APP + "/android-native/engine/src/test/resources/golden/routing-leaves.json"
REGISTRY = "https://r4topunk.github.io/boar-research/data/experiments.json"


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode("utf-8")


# ---------------------------------------------------------------- part 1
# NUM as in Calculators.kt: a thousands form or a plain decimal.
NUM = r"(\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"
RATE = re.compile(
    r"\b1\s*(?:u\.?s\.?\s+)?(d[óo]lar(?:es)?(?: americanos?)?|us\$|usd|euros?|eur|€|libras?|gbp|real|brl|r\$|dollars?(?: us)?)"
    r"\s*(?:vale|valem|=|equals|is worth|is)\s*" + NUM + r"\s*([A-Za-zÀ-ÿ$€£]+(?: [A-Za-zÀ-ÿ]+)?)?", re.I)
AMOUNT = re.compile(NUM + r"\s*(?!%)([A-Za-zÀ-ÿ$€£]+)?", re.I)
PERCENT = re.compile(NUM + r"\s*%")
THOUSANDS = re.compile(r"^\d{1,3}(?:[.\s]\d{3})+$")


def parse_number(raw):
    """Calculators.parseNumber, verbatim: no branch for the thousands form."""
    s = re.sub(r"\s", "", raw)
    if "," in s and "." in s:
        return float((s.replace(".", "").replace(",", ".", 1)) if s.rfind(",") > s.rfind(".") else s.replace(",", ""))
    if "," in s:
        return float(s.replace(",", "")) if re.search(r",\d{3}$", s) else float(s.replace(",", ".", 1))
    return float(s)                      # "12.000" -> 12.0   <-- the bug


def currency(q, fixed_thousands=False):
    rate = RATE.search(q)
    if not rate:
        return None
    r = parse_number(rate.group(2))
    rest = q.replace(rate.group(0), " ", 1)
    am = AMOUNT.search(PERCENT.sub(" ", rest))
    if not am or not r > 0:
        return None
    raw_amount = am.group(1)
    if fixed_thousands and THOUSANDS.match(re.sub(r"\s", "", raw_amount)):
        amount = float(re.sub(r"[.\s]", "", raw_amount))
    else:
        amount = parse_number(raw_amount)
    unit_from = (am.group(2) or rate.group(3) or "").strip()
    cur = rate.group(1)
    unit_to = "US dollars" if re.sub(r"es$", "", cur, flags=re.I).lower().startswith("d") else cur
    return f"{amount:g} {unit_from} ÷ {r:g} = {amount / r:.2f} {unit_to}"


def part1():
    g = json.loads(get(GOLDEN))
    cases = [c for c in g["calculate"] if c.get("out", {}) and c["out"].get("kind") == "currency"]
    print(f"golden fixtures with kind=currency: {len(cases)}")
    for c in cases:
        print(f"\n  Q: {c['q']}\n  expected by the test suite: {c['out']['text']}")
    print("\n  Recomputing the same question with the thousands form parsed as a number:")
    q = "1 u.s. dollar equals 150 yen; dinner was 12.000 yen with 10% service"
    print(f"    as shipped : {currency(q)}")
    print(f"    with the fix: {currency(q, fixed_thousands=True)}   (12.000 yen = 80.00 USD)")

    print("\n  The three currency fixtures all convert an amount given in the QUOTE currency.")
    print("  Hand-evaluating the other two directions of the same six lines:")
    for q, want in [
        ("1 dollar is worth 0.92 eur: how many eur is 50 dollars?", "46.00 eur"),
        ("1 euro = 1.09 dollars: how many dollars is 50 euros?", "54.50 US dollars"),
    ]:
        print(f"    Q: {q}\n      app: {currency(q)}\n      correct: {want}")


# ---------------------------------------------------------------- part 2
def part2():
    d = json.loads(get(REGISTRY))
    rows = d["experiments"] if isinstance(d, dict) else d
    bad = [r for r in rows if r.get("verdict") == "adopted" and r.get("closed_row")
           and re.search(r"closed|not adopted", r.get("verdict_detail") or "", re.I)]
    print(f"\nregistry rows: {len(rows)}")
    print("verdict=adopted, yet carrying a closed_row and a detail that says closed/not adopted:")
    for r in bad:
        print(f"  {r['id']:7s} closed_row={r['closed_row']:4s} detail: {(r.get('verdict_detail') or '')[:96]}")
    counts = {}
    for r in rows:
        counts[r.get("verdict")] = counts.get(r.get("verdict"), 0) + 1
    nogain = counts.get("closed", 0) + counts.get("not-detected", 0)
    print(f"\n  published (llms.txt): '387 recorded experiments (215 ended without a gain)'")
    print(f"  recomputed as published: {nogain} without a gain, {len(rows) - nogain} otherwise")
    print(f"  after fixing the {len(bad)} rows: {nogain + len(bad)} / {len(rows) - nogain - len(bad)}")


if __name__ == "__main__":
    part1()
    part2()
