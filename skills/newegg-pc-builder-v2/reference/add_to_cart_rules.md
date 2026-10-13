# Add to Cart Rules (Step 9b)

Load this file only when actually rendering the Add to Cart action — button
styling for cards, plus the link-construction rule (needed regardless of
card vs. Markdown). Referenced from SKILL.md's Step 9.

## 🚨 Mandatory on every platform (hard requirement — this has been dropped in practice, e.g. on AngX)

Add to cart is not a Claude-only enhancement. Every full-build
presentation, on any Agent platform, must end with either the styled card
button (Claude, `visualize:show_widget` confirmed present) or the plain
Markdown link below (everywhere else, including platforms with no
button-rendering capability at all). The Markdown form requires no special
tool — there is no environment where it's legitimate to have neither. See
SKILL.md's pre-send gate, which checks for this explicitly before any
output is sent.

## Button styling (Claude card only)

Markdown path (Step 9c) doesn't need button styling — just a plain link:
`🛒 [Add to cart](URL)`, same URL rule as below.

For a Claude card, one fixed button at the bottom (hard requirement, don't
change the color):

| Button | Copy | Background | Text color | Notes |
|------|------|--------|--------|------|
| Add to cart | `Add to cart` | `#EF9F27` (amber 400) | `#412402` (amber 900) | Icon: `ti-shopping-cart` |

Implementation notes:
- `width:100%` (single button, no `flex:1` split needed)
- Colors go in the `style` attribute with `!important` — the component's
  default button style otherwise overrides a plain class
- Icon: `ti-shopping-cart`, 16px, 4px spacing from text
- Navigate via `onclick="openLink('...')"` — don't wrap in `<a>`

**⚠️ Customize button removed**: it would need to POST to Newegg's
customization page, but the widget sandbox's CSP allowlist doesn't include
Newegg's domain (JS `fetch()` would be silently blocked, not even show a
confirmation dialog), and native-form-submission behavior was never
verified either. Too much risk/uncertainty — removed outright, only Add to
cart remains. If reintroducing similar functionality later, confirm the
endpoint supports GET/URL-navigation first — don't default to POST/fetch.

**⚠️ Platform limitation (not a bug, can't be bypassed)**: clicking Add to
cart triggers Claude's forced "Open external link" confirmation dialog —
this is a platform security mechanism preventing generated content from
silently navigating or submitting data, and no widget code can close or
skip it. If a user asks why, explain it's a platform security design — don't
attempt workarounds (auto-submitting forms, hidden iframes, etc.); that
itself would violate security principles.

**Disclaimer placement (see SKILL.md Step 10)**: on the Claude card, add
the Step 10 disclaimer line directly below the Add to cart button, inside
the same `widget_code` payload — small/light text (e.g. `font-size: 12px;
color: var(--text-muted);`). It is part of the card, not separate chat
text sent after the tool call.

## Link construction rule (hard requirement)

```
https://secure.newegg.com/api/shop/add?Submit=Add&ItemList=<item1>.PCDIY4|<qty1>%2C<item2>.PCDIY4|<qty2>%2C...
```

1. For every component actually on the current card, use its **raw**
   `itemNumber` — **no N82E168 conversion** (unlike the product-link rule)
   — whether standard (`19-113-842`) or marketplace format
   (`1HU-024C-000C2`), both used as-is
2. Format each as `<itemNumber>.PCDIY4|<quantity>`, quantity defaults to
   `1` unless the user asked for more of a specific part
3. Join with `%2C` (URL-encoded comma)
4. Final URL = `https://secure.newegg.com/api/shop/add?Submit=Add&ItemList=`
   + the joined string
5. **Components the user removed/replaced** (e.g. "I already have a
   cooler") are excluded from the list — only include what's still on the
   card and needs purchasing
6. If a component has no `itemNumber` (shouldn't normally happen), skip it
   and note "one component is missing a product number, so the add-to-cart
   link may be incomplete" — don't fabricate one

**Example** (CPU `19-113-842`, motherboard `13-162-187`, GPU `14-131-886`):
```
https://secure.newegg.com/api/shop/add?Submit=Add&ItemList=19-113-842.PCDIY4|1%2C13-162-187.PCDIY4|1%2C14-131-886.PCDIY4|1
```
