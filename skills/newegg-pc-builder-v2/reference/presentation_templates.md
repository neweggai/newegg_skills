# Presentation Templates (Step 9)

Load this file when actually rendering a card or Markdown table — it's the
lookup content for *how* to build the output, not the decision logic for
*whether* to (that stays in SKILL.md's Step 9 trigger checklist).

## Card UI language (hard requirement)

All copy inside a card or Markdown table — category labels, headers
(Part/Model/Price), status text (Compatible/Power headroom), promo/combo
notes, action-link copy — **always English**, regardless of conversation
language. End customers are US-based; the presented result is a
customer-facing document, not internal chat. This is independent of the
"Output Language" rule for explanatory text outside the card (see SKILL.md).

**Glossary** (idiomatic e-commerce terms, not literal translation):

| Concept | English term |
|------|------|
| Part category header | Part |
| Model header | Model |
| Price header | Price |
| Recommended config | Recommended build |
| Popular config | Popular |
| Value config | Valued |
| Over budget +12% | 12% over budget |
| Near budget | Near budget |
| Within budget | Within budget |
| Compatibility passed | Compatibility verified |
| Sufficient PSU headroom | Power headroom: good |
| Tight PSU headroom | Power headroom: tight |
| Excessive PSU headroom | Power headroom: excessive |
| Cooler supplied by customer | Cooler supplied by customer |
| Promo code savings (manual entry) | Promo code savings (apply at checkout) |
| Combo savings (automatic) | Combo savings (applied automatically) |

**This has been violated in practice (e.g. on the AngX platform)**: a combo
note rendered as `Combo savings (applied automatically): 总套装再省 $25.00`
— English label, Chinese content, and it also dropped which specific
components contributed. Both parts are wrong: everything inside the
card/table region must be English regardless of conversation language, and
a combo/promo note must name the actual components (e.g. "CPU +
motherboard + storage bundled together save $25.00"), not just state an
amount. Same standard applies to compatibility/power badges — don't append
translated or explanatory clauses onto a badge line; extra explanation
belongs in the surrounding response text, in the user's language, not
inside the card.

## Component-list table layout (hard requirement, fixed 3-column format)

Component category (CPU/motherboard/GPU/etc.) | model name (linked per
`reference/product_link_rules.md`) | unit price. Never omit the unit price
— it's part of value transparency (Step 6). Price = `unitPrice −
instantRebateAmount` per item (see SKILL.md Step 6's price waterfall) —
never the raw `unitPrice` alone, and never estimated by splitting the total.

## Compatibility / power status badges (Claude card only)

**Hard requirement — this is not optional styling, it's the visual signal
the user relies on to tell "passes cleanly" from "works but tight" at a
glance.** On the Claude card (not Markdown, which stays plain ✅/⚠️ text
per the Channel note below), render Step 5a's compatibility result and
Step 5b's power result as colored pill badges, not plain text next to a
colored icon:

- **Passes cleanly** (Step 5a `isCompatible: true`; Step 5b actual ≥
  `recommended_psu_watts`) → green pill: `background: var(--bg-success);
  color: var(--text-success)`, `ti-check` icon.
- **Soft Issue** (Step 5b "tight but sufficient" — actual between
  `total_watts` and `recommended_psu_watts`; or a compatible-but-notable
  tradeoff like RAM speed below recommended) → amber/warning pill:
  `background: var(--bg-warning); color: var(--text-warning)`,
  `ti-alert-triangle` icon. Label the specific concern (e.g. "Power
  headroom: tight", "RAM speed below recommended") rather than a bare
  "Warning."
- **Hard Conflict** never reaches this badge — per SKILL.md Step 5's
  handling rules, a Hard Conflict gets fixed (component swapped,
  re-verified) before Step 9 renders anything. There is no red/danger
  variant of this badge; if no fix exists, that's the "surface the issue
  and stop" path (SKILL.md Step 5, handling rule 1), not a red badge on an
  otherwise-presented card.

Markup pattern (pill shape, `border-radius: 999px`, `padding: 4px 10px`,
`font-size: 12px`, icon at `14px` with 4px gap):

```html
<span style="display:inline-flex; align-items:center; gap:4px; background:var(--bg-success); color:var(--text-success); font-size:12px; font-weight:500; padding:4px 10px; border-radius:999px;"><i class="ti ti-check" style="font-size:14px;" aria-hidden="true"></i>Compatibility verified</span>
<span style="display:inline-flex; align-items:center; gap:4px; background:var(--bg-warning); color:var(--text-warning); font-size:12px; font-weight:500; padding:4px 10px; border-radius:999px;"><i class="ti ti-alert-triangle" style="font-size:14px;" aria-hidden="true"></i>Power headroom: tight</span>
```

This is the same green/amber vocabulary the Out-of-stock badge below
already uses — apply it consistently rather than treating compatibility/
power as plain text while OOS gets a badge.

## Out-of-stock labeling (per Step 5d)

A confirmed-OOS line item gets a visible label — a small "Out of Stock"
badge (warning color, not success/green) in the card, or `⚠️ Out of Stock`
in Markdown. Never present it as normal, but never drop the whole tier over
one flagged line either.

## Step 9c — Universal Markdown template (default baseline)

Must carry the same information as the card — don't drop promo codes,
combo savings, or verification results just because the format changed.
Repeat this block once per tier for multi-tier output:

```markdown
## Recommended build — $1,644.83 ~~$1,763.83~~ (10% over budget)

| Part | Model | Price |
|------|-------|-------|
| CPU | [AMD Ryzen 5 9600X](https://www.newegg.com/p/N82E16819113844) | $199.99 |
| Motherboard | [ASRock X870 STEEL LEGEND](https://www.newegg.com/p/N82E16813162165) | $169.99 |
| GPU | [SAPPHIRE RX 9060 XT 16GB](https://www.newegg.com/p/N82E16814202457) | $519.99 |
| RAM | [32GB DDR5 6000](https://www.newegg.com/p/N82E16820236991) | $489.99 |
| Storage | [Team T-FORCE G50 1TB](https://www.newegg.com/p/N82E16820985133) | $189.99 |
| Case | [LIAN LI ATX Mid Tower](https://www.newegg.com/p/2AM-000Z-000D6) | $82.99 |
| PSU | [MSI 650W Bronze](https://www.newegg.com/p/N82E16817701013) | $64.99 |
| Cooler | [be quiet! Pure Rock Pro 3](https://www.newegg.com/p/N82E16835269028) | $45.90 |

**Promo code savings (apply at checkout):**
- CPU: code `BTS2115` → -$25.00
- Storage: code `APC972356` → -$20.00

**Combo savings (applied automatically):** CPU + RAM + Storage bundled
together save an extra $74.00

✅ Compatibility verified · ✅ Power headroom: good

🛒 [Add to cart](https://secure.newegg.com/api/shop/add?Submit=Add&ItemList=...)

*Prices, promo codes, and stock status shown are subject to change — please confirm final pricing at checkout on Newegg.com.*
```

Key points:
- Title line uses `~~strikethrough~~` for the price comparison, budget
  status in parentheses
- Parts table is strictly 3 columns
- Promo/combo savings always shown via bold sub-heading + list
- Compatibility/power results use ✅/⚠️ plus brief text, not HTML badges
- Add to cart is a plain Markdown link (same effect as the card button);
  even where links don't render, the full URL is still readable/copyable

## Channel note

The card depends on Claude's Visualizer component and is an **optional
enhancement only** — the Markdown template above is the required universal
baseline every platform must be able to produce. Never force-output HTML
that can't render.
