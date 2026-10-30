# Bounty #1520 — LabRat's deterministic currency answer is 1000× low, and its golden test certifies the wrong value

Claim for poidh **#1520 "Audit a Month of Offline AI Research"** (Base, onChainId 534).

The record's thesis lists **"code-computed arithmetic"** among the five things the harness does around
a 1.7B model, and the comment above `Calculators` explains why: the compact model *"got … currency with
a given rate … wrong"*. Currency conversion was therefore moved out of the model into deterministic
Kotlin. It is still wrong, in two independent ways, and the fixture that should catch it pins one of
the wrong answers as the expected output.

Everything below comes from public sources. `python3 audit.py` reproduces every number here.

---

## 1. `parseNumber` and `NUM` disagree about the thousands separator: "12.000" becomes 12

`Calculators.kt:16` defines the number token as a **thousands-aware** pattern:

```kotlin
private const val NUM = """(\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"""
```

so `12.000` is matched by the group that means *twelve thousand*. `parseNumber` (`:21-29`) then handles
`,` and `.` but has **no branch for that form**:

```kotlin
if (',' in s) return …                    // 1,200 -> 1200
if ('.' in s) return JsNumber.parse(s)    // 12.000 -> 12.0   <-- JS Number() semantics
```

`JsNumber.parse("12.000")` matches its decimal regex and returns `12.0`, so the app answers:

> **Q.** "1 u.s. dollar equals 150 yen; dinner was 12.000 yen with 10% service"
> **A.** `12 yen ÷ 150 = 0.08 US dollars.`

A **1000× error**, and a self-evidently absurd one: the answer's own text says "12 yen" about a
12,000-yen dinner. The correct value is 80.00 USD (88.00 with the service charge).

The destroyed convention is the Spanish/German/Italian/Brazilian one — dot as thousands separator,
which is exactly why `NUM` has that branch, and the app ships Spanish packs and `ES_END` spelling
logic. An ES user writing `12.000` gets a number three orders of magnitude off, silently.

**It is enshrined.** `android-native/engine/src/test/resources/golden/routing-leaves.json` (fixture of
`RoutingLeavesGoldenTest`) contains that question with `"text": "12 yen ÷ 150 = 0.08 US dollars."` as the
**expected** value. The goldens were generated from the implementation rather than from an independent
computation, so the defect is not a coverage gap: it is the certified behaviour. Re-running the suite
confirms it.

Fix — `patch/parseNumber.kt.diff`, 4 lines:

```kotlin
private val THOUSANDS = JsRegex.re("""^\d{1,3}(?:[.\s]\d{3})+$""")
fun parseNumber(raw: String): Double {
    val s = WS_ANY.replace(raw, "")
    if (THOUSANDS.containsMatchIn(s)) return JsNumber.parse(s.replace(".", ""))
    …
}
```

With that branch the same question yields `12000 yen ÷ 150 = 80.00 US dollars`.

## 2. `currency()` implements one quadrant of the conversion matrix and mislabels the rest

`Calculators.kt:92-111` parses `1 <base> = r <quote>` and then always performs the same operation:

```kotlin
val unitTo = if (ES_END.replaceFirst(cur,"").lowercase().startsWith("d")) "US dollars" else cur
val converted = amount / r
```

`cur` is the rate's **base** and `r` is *quote per base*, so `amount / r` is only correct when the
amount is already in the **quote** currency — and `unitTo` labels the result with the **base**, so
when the amount is in the base the answer is numerically *and* dimensionally wrong:

| rate | question | LabRat | correct |
|---|---|---|---|
| 1 USD = 0.92 EUR | how many **eur** is **50 dollars**? | `50 dollars ÷ 0.92 = 54.35 US dollars` | 46.00 EUR |
| 1 EUR = 1.09 USD | how many **dollars** is **50 euros**? | `50 euros ÷ 1.09 = 45.87 euro` | 54.50 USD |
| 1 USD = 0.92 EUR | 50 eur | `54.35 US dollars` ✔ | 54.35 USD |

All **three** currency fixtures in the golden file are quote-currency amounts (baht, eur, yen) — the
one column that works. The other column has no fixture at all, which is why the second row survives.

Fix: keep base and quote, pick the direction from the amount's unit, multiply or divide accordingly,
and label with the target currency instead of guessing from the first letter of `cur`.

## 3. (Secondary) Six registry rows contradict the closed row they point at

`experiments.json` rows carry `verdict` plus a `closed_row` pointer into
`rnd/research/coordinator/CLOSED.md`. Six rows say `adopted` **and** point at a closure whose own
detail says the opposite:

| row | closed_row | its own `verdict_detail` |
|---|---|---|
| X-019 | R57 | `closed (VG-S2 FAIL … VG line CLOSED)` |
| X-052 | R63 | `closed (NOT ADOPTED: G3 FAIL 45 % < 60 %)` |
| X-055 | R61 | `closed: NOT ADOPTED as frozen (G3 58.1% < 90% …)` |
| X-056 | R62 | `closed: NOT ADOPTED. The HFU-FIX family is closed …` |
| X-084 | R36 | `closed: no knob adopted, P0 flags unchanged` |
| X-182 | R91 | `closed: NO (Haiku, dev 180)` |

`R63`'s report (`arms/followq/FOLLOWQG.md`) opens with "**NOT ADOPTED. G3 FAIL (45 %, bar ≥ 60 %)**".
These are not the disclosed trade-off exceptions (X-014, X-403 explain their adoption in the row):
here nothing in the row acknowledges an adoption.

Effect on the published ledger: `llms.txt` states *"387 recorded experiments (215 ended without a
gain)"*. The 215 is `closed` (187) + `not-detected` (28); after correcting the six rows it is
**221 without a gain / 166 otherwise**, not 172. The schema already added a `not-detected` value to
keep these labels exact, so the field is meant to be exact.

---

## What I checked and did *not* find

- **The headline numbers reproduce.** From the raw judgments and serving traces: U-total 0.164536
  (0.127–0.205) and 0.242450 (0.194–0.296), 0 wins in 71 items under both families, the desktop twin
  0.163929 / 0.244985, and the paired F-2239 deltas +0.0030 / −0.0067, CIs included — all identical
  to the published values. The record's item-level arithmetic is sound; what fails is a code path the
  record trusts, plus one bookkeeping field.
- **No v0.4 item exercises currency** (0 of 75 by keyword scan), so this defect moves no published
  number: it is a bug in the shipped app, not a scoring error. It matters because the harness's claim
  is precisely that its deterministic paths are where you stop worrying about the small model.
- Not claimed here (already raised by others, claims 9221/9225/9227): HealthGate licensing, the
  FACT-AVAIL pack subset, the `m1_agg` pool-then-threshold bug.

## Reproduce

```
python3 audit.py     # fetches the golden fixture + the live experiments.json, prints every number above
```

`RESULTS.txt` is the captured run. Files: `audit.py`, `RESULTS.txt`, `patch/parseNumber.kt.diff`,
`card1520.png`.
