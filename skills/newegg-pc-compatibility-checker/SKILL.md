---
name: newegg-pc-compatibility-checker
description: Verify whether a set of specific PC hardware items are compatible with each other using Newegg's real PC Builder compatibility engine. Use when the user has parts in mind (model names or Newegg item numbers) and asks whether they work together — "do these work together", "will this GPU work with my PSU", "can this RAM go on this motherboard", "is this build compatible", "这些硬件兼容吗", "这个显卡能配我的电源吗", "我想升级显卡，原来的电源够不够". Trigger when the user names two or more specific hardware items and wants a verdict. Do NOT use for from-scratch build recommendations where the user has not picked specific parts.
allowed-tools: bash
---

# PC Compatibility Checker

Verify hardware compatibility via Newegg's MCP endpoints over HTTP using standard JSON-RPC. Use the
`bash` tool to call the endpoints — no MCP client registration required.

This skill does one thing: route the user's parts through Newegg's PC Builder compatibility
endpoint and report what it says. It does not recommend new builds from scratch — that is outside
scope.

## Agent Execution Rules

* **Reply in the user's language.** Detect the language of the user's question and produce the
  entire response in that language — headings, explanations, fix proposals, everything. Chinese
  question → Chinese reply. English question → English reply. Japanese question → Japanese reply.
  Do not mix unless the user mixes first. The only exception is that raw data (item numbers,
  model names, the original English `reasonTraces` string in parentheses) stays as-is.
* **Do not** guess compatibility from your own hardware knowledge. That is the exact failure mode
  this skill exists to prevent.
* **Do not** ask for clarification when the user already gave you the parts. Infer item numbers /
  names from their message and call immediately.
* Use the **`bash`** tool to run the curl commands below.
* On curl failure or invalid JSON, report the error directly. Do not fall back to your own
  knowledge to produce a verdict.

## Endpoints

**Required header on every request**: all calls to `apis.newegg.com/ex-mcp/...` must carry `x-skill: newegg-pc-compatibility-checker` in addition to `Content-Type`. It identifies the calling skill to the endpoint — include it even when you assemble a request by hand rather than copying an example below.

| Purpose | Endpoint |
| --- | --- |
| Compatibility check | `https://apis.newegg.com/ex-mcp/endpoint/ext-pc-builder` |
| Product search | `https://apis.newegg.com/ex-mcp/endpoint/product-search` |

product-search is only needed when the user gives you a model name without an item number —
it resolves `name → ItemNumber`. When the user already gave item numbers, go straight to
pc-builder.

**Newegg product link format**: every item number resolves to a working product page at
`https://www.newegg.com/p/<ItemNumber>` (short-hyphenated form, e.g.
`https://www.newegg.com/p/19-113-884` — this redirects to the canonical product URL and always
works). Every link you actually show the user must be the **full UTM-tagged form** per
[`references/product_link_rules.md`](./references/product_link_rules.md) (the same convention
`newegg-pc-builder-v2` uses) — never the bare `/p/<ItemNumber>` form. **Attach it whenever you
display an item in the response, as a markdown hyperlink on the item's name**:

```
[<name> (<item number>)](https://www.newegg.com/p/<item number>?Item=<item number>&utm_source={platform}&utm_medium=ai_skill&utm_campaign=aik_{platform}_pc-compatibility-checker&utm_content=newegg-pc-compatibility-checker)
```

for every checked part and every replacement part you propose. Never show the raw URL as its own
table column or its own line next to the name; that's redundant. Every worked example in this
file (Response format below included) already shows the tagged form — copy that shape, not a
shortened one, even though the query string makes it visually longer.

**Price**: product-search results include a `Price.FinalPrice` (numeric) and `Price.CurrencyCode`
field on each product. Whenever you already have a product-search result for an item — which you
will, either from resolving a model name or from the item-number verification step below — carry
its price into the report as well. Show it in the price column next to the item, formatted with
the currency (e.g. `$699.00`). Do not fetch a price you don't already have just to fill this in,
and never invent or estimate one — if a given item's price genuinely isn't available (e.g. the
user supplied an item number you deliberately did not re-verify — which shouldn't happen per the
rule below), leave the price cell blank rather than guessing.

## The flow

### Step 1 — Get every part as an item number

Look at what the user provided:

* **They gave item numbers** (e.g. `19-113-938`) → **verify each one before trusting it**, then
  go to Step 2. Always use the **short hyphenated format** (`19-113-938`), never the long URL
  form (`N82E16819113938`).

  **Why verify:** pc-builder does not validate that a submitted item number belongs to a real
  catalog product. A typo'd or hallucinated item number is silently treated as "no data" and
  the combo comes back `isCompatible: true` with no error and no `incompatibleItems` — visually
  identical to a genuine compatible verdict. Do not skip this just because it looks like a
  legitimate ID.

  **How to verify:** call **product-search** with the item number itself as the `query`. This
  endpoint is a general keyword search, not an exact-ID lookup, so it returns loosely-matching
  results even for numbers that don't exist — the check is whether any returned product's
  `ItemNumber` field is an **exact match** for the number you searched, not whether the search
  returned results at all.
  * Exact match found → confirmed real, proceed. You now also have the product name and can use
    it for the Newegg link / display name.
  * No exact match → treat it exactly like a `product-search: total 0` case (see below): tell the
    user this item number wasn't found in the catalog and confirm before proceeding with anything.
* **They gave model names** (e.g. "Ryzen 9 9950X3D" + "ASUS B760M-AYW WIFI D4") → call
  **product-search** once per part (in parallel) to resolve each name into an `ItemNumber`.
* **Mixed** → only search for the parts that do not already have item numbers.

product-search returns `ItemNumber` directly in the short-hyphenated format — that is everything
you need to hand to pc-builder. Do not call any other endpoint for the name → item-number step.

If a search returns multiple candidates, pick the one whose `WebDescription` most closely matches
the user's wording. Only ask the user to disambiguate when it is truly ambiguous (e.g. "DDR4 or
DDR5 version of this kit?"). Do not ask three clarifying questions when one will do.

**If product-search returns `total: 0` for a part**, do NOT silently substitute a similar part and
proceed. The correct action is:

1. Tell the user plainly that the part was not found in Newegg's catalog (likely out of stock or
   not carried). Name the specific part the user asked for.
2. Offer to try a close substitute and describe what the substitute would be (same platform /
   generation / price tier), but **wait for the user's confirmation** before calling pc-builder
   with the substitute.
3. If the user declines the substitute, stop. Do not fabricate an item number from your own
   knowledge — pc-builder will reject it and the verdict will be meaningless.

Silently swapping in a different part is a worse failure mode than reporting the search gap,
because the user will not realize the final compatibility report is about a part they did not ask
about.

### Step 2 — Call pc-builder once with every item

Call `comboCompatibleAll` with a **space-separated list** of short-hyphenated item numbers in a
single `itemNumber` string. Do not call pairwise — pc-builder accepts the full set and computes
conflicts internally.

```
curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/ext-pc-builder" \
  -H "Content-Type: application/json" \
  -H "x-skill: newegg-pc-compatibility-checker" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "comboCompatibleAll",
      "arguments": {
        "businessId": 2,
        "itemNumber": "<ITEM1> <ITEM2> <ITEM3>"
      }
    }
  }'
```

* `businessId` is always **`2`** (fixed).
* `itemNumber` is a **space-separated** string of short-hyphenated item numbers — e.g.
  `"19-113-938 13-144-674"`.

> If the call returns a tool-not-found error, first run `tools/list` to discover the correct tool
> name:
>
> ```
> curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/ext-pc-builder" \
>   -H "Content-Type: application/json" \
>   -H "x-skill: newegg-pc-compatibility-checker" \
>   -d '{"jsonrpc":"2.0","id":0,"method":"tools/list"}'
> ```

#### pc-builder response shape

Parse the path:

```
response → result.content[0].text → (parse as JSON) → verdict
```

Fields on the verdict object:

| Field | Description |
| --- | --- |
| `isCompatible` | `true` → all parts compatible. `false` → at least one conflict |
| `incompatibleItems[]` | Present only when `isCompatible: false`. One entry per conflicting pair |
| `incompatibleItems[].itemNumber` | One side of the conflict |
| `incompatibleItems[].relatedItemNumber` | The other side of the conflict |
| `incompatibleItems[].reason` | Single summary line of the conflict |
| `incompatibleItems[].uncompatibleInfo` | Usually duplicates `reason` |
| `incompatibleItems[].reasonTraces[]` | **Array of every specific rule that failed.** Always read this, not just `reason` |

### Step 3 — Report the verdict honestly

**If `isCompatible: true`:** Say so plainly, list what was checked — each item with its Newegg
link (`https://www.newegg.com/p/<ItemNumber>`, UTM-tagged per `references/product_link_rules.md`) — and stop. Do not invent caveats from your own
knowledge beyond the PSU exception below.

**Exception — PSU wattage disclosure.** pc-builder's rules cover sockets, chipsets, memory type,
physical fit, and electrical interfaces — but they **do not validate that a PSU's wattage meets
the GPU manufacturer's recommended minimum**. So a 750W PSU paired with an RTX 5090 will return
`isCompatible: true` even though Nvidia recommends 1000W.

Whenever a PSU is among the checked items AND `isCompatible: true`, do not just print a generic
warning — try to get an actual number first:

1. **Check whether the `newegg-psu-calculator` skill is installed/available in this session.**
2. **If it is available**, invoke it with the CPU/GPU/RAM/storage from this build (as much as you
   know) to get a real `recommended_psu_watts` figure, then compare it against the PSU actually in
   the build:
   * PSU wattage ≥ recommended → state plainly that the PSU is sufficient, citing both numbers.
   * PSU wattage < recommended → flag it clearly as undersized, show both numbers side by side,
     and propose a specific replacement PSU (Step 4) at or above the recommended tier, with its
     Newegg link.
3. **If `newegg-psu-calculator` is not available**, do not attempt the wattage math yourself —
   append this line instead:

   > ⚠️ pc-builder does not verify PSU recommended wattage against the GPU's requirements, and the
   > `newegg-psu-calculator` skill isn't available in this session to calculate it precisely.
   > Install that skill for an exact recommendation, or check it yourself with Newegg's official
   > calculator: https://www.newegg.com/tools/power-supply-calculator

This is not "adding a caveat from your own knowledge" — it is a known, documented limitation of
the MCP. Prefer a precise, skill-calculated answer when `newegg-psu-calculator` is available; fall
back to pointing the user at the official tool only when it isn't.

**If `isCompatible: false`:** Walk through `incompatibleItems[]` one entry at a time. For each
entry:

1. Refer to the two conflicting items using **whatever the user gave you in their original
   question**, each with its Newegg link:
   * User gave model names → use those names (e.g. "Ryzen 9 9950X3D ↔ ASUS B760M-AYW").
   * User gave bare item numbers → use the item numbers (e.g. "19-113-938 ↔ 13-144-674").
   * User gave a mix → use names where they gave names, item numbers where they gave item
     numbers. Do not do a lookup just to pretty-print — only fetch the link, not a renamed label.
2. List **every** entry in `reasonTraces` — not just `reason`. Each trace is a separate failed
   rule and the user deserves to see all of them.
3. Translate each `reasonTrace` into the user's language (per the top-level "Reply in the user's
   language" rule), with the original English string in parentheses for reference. The MCP
   returns slightly stilted English (`"doesn't support with Socket AM5"`) that reads better
   translated — but the user still benefits from seeing the original so they can look up the
   exact rule if needed.

### Step 4 — Suggest a fix and re-verify

After explaining the conflict, propose a concrete fix:

| Conflict type | Typical fix |
| --- | --- |
| Socket / chipset / DDR-generation mismatch | Swap the smaller/cheaper side (usually the motherboard or RAM, not the CPU) |
| PSU undersized vs. GPU (see PSU wattage disclosure above) | Suggest a specific replacement PSU at/above the calculated recommended wattage |
| Physical fit (case clearance, cooler height) | Swap a part of the same category |

Use **product-search** to find the replacement part, then **call pc-builder again** with the
updated item list to verify. Do not declare the fix valid from your own reasoning — re-run
pc-builder. Iterate until `isCompatible: true` or the user changes scope.

**Every replacement part you propose must include its Newegg product link**
(`https://www.newegg.com/p/<ItemNumber>`, UTM-tagged per `references/product_link_rules.md`) so the user can go buy it directly — a fix suggestion
with no link makes the user do a manual search for something you already found.

## Response format

Use this structure when reporting the verdict to the user. **The Newegg link is never its own
column or its own line — it's a markdown hyperlink on the item's name itself**
(`[<name> (<item number>)](https://www.newegg.com/p/<item number>)`), so the table stays compact
and the link is still one click away. All headings, labels, and explanations in the template below
must be translated into the user's language; the English shown here is a structural placeholder —
do not ship English section headers (`## Compatibility check`, `### Suggested fix`, etc.) to a
non-English-speaking user.

**Compatible:**

```
## Compatibility check: ✅ Compatible

| Part | Model / Item # | Price |
| --- | --- | --- |
| <category> | [<user's name for item 1> (<item number>)](https://www.newegg.com/p/<item number>?Item=<item number>&utm_source={platform}&utm_medium=ai_skill&utm_campaign=aik_{platform}_pc-compatibility-checker&utm_content=newegg-pc-compatibility-checker) | $<price> |
| <category> | [<user's name for item 2> (<item number>)](https://www.newegg.com/p/<item number>?Item=<item number>&utm_source={platform}&utm_medium=ai_skill&utm_campaign=aik_{platform}_pc-compatibility-checker&utm_content=newegg-pc-compatibility-checker) | $<price> |

All parts are compatible according to Newegg PC Compatibility Checker.

[If a PSU is included: PSU wattage line per the Exception rule above — either a
newegg-psu-calculator-backed verdict with both wattages, or the official calculator link.]
```

**Incompatible:**

```
## Compatibility check: ❌ Incompatible

**Conflict 1: [<name1> (<item1>)](https://www.newegg.com/p/<item1>?Item=<item1>&utm_source={platform}&utm_medium=ai_skill&utm_campaign=aik_{platform}_pc-compatibility-checker&utm_content=newegg-pc-compatibility-checker) ↔ [<name2> (<item2>)](https://www.newegg.com/p/<item2>?Item=<item2>&utm_source={platform}&utm_medium=ai_skill&utm_campaign=aik_{platform}_pc-compatibility-checker&utm_content=newegg-pc-compatibility-checker)**
- <reasonTraces[0] translated> (original: <reasonTraces[0]>)
- <reasonTraces[1] translated> (original: <reasonTraces[1]>)

**Conflict 2: ...**

### Suggested fix
| Conflict | Replacement | Price |
| --- | --- | --- |
| Conflict 1 | [<specific replacement part name> (<item number>)](https://www.newegg.com/p/<item number>?Item=<item number>&utm_source={platform}&utm_medium=ai_skill&utm_campaign=aik_{platform}_pc-compatibility-checker&utm_content=newegg-pc-compatibility-checker) | $<price> |

### Re-verification
[call pc-builder again with the replacement → report new isCompatible]
```

## Hard rules

* **Attach a Newegg product link to every item you display, as a hyperlink on its name, always
  UTM-tagged** per [`references/product_link_rules.md`](./references/product_link_rules.md) —
  `[<name> (<item number>)](https://www.newegg.com/p/<ItemNumber>?Item=<ItemNumber>&utm_source={platform}&utm_medium=ai_skill&utm_campaign=aik_{platform}_pc-compatibility-checker&utm_content=newegg-pc-compatibility-checker)`
  — never the bare `/p/<ItemNumber>` link with no query string. Applies whether it's a part the
  user asked about or a replacement you're suggesting. Never put the raw URL in its own table
  column or its own line; that's redundant next to a named hyperlink.
* **Show each item's price** (from `Price.FinalPrice` / `Price.CurrencyCode` on the product-search
  result you already fetched for the link/verification step) in its own table column. Never
  invent or estimate a price — leave the cell blank if you genuinely don't have one.
* **Prefer `newegg-psu-calculator` for the PSU wattage exception.** Check whether it's available
  and call it for an exact recommended wattage before falling back to the generic disclaimer /
  official calculator link.
* **Item numbers go to pc-builder in short hyphenated format** (`19-113-938`), not the long form
  (`N82E16819113938`).
* **Never claim compatibility without an `isCompatible: true`** from pc-builder. No verdicts
  derived from your own knowledge. Ever.
* **Never trust `isCompatible: true` for an item number that wasn't verified to exist** (either
  resolved via product-search from a model name, or exact-matched via product-search when the
  user gave the number directly). pc-builder returns `isCompatible: true` for nonexistent item
  numbers with no error — that is not a real verdict.
* **Never claim incompatibility without an `isCompatible: false`** from pc-builder. Even for
  "obvious" cases (AMD CPU + Intel motherboard), still call pc-builder so the user sees the
  authoritative verdict and the specific reasons.
* **Read `reasonTraces`, not just `reason`** — the array has more detail than the summary string.
* **Reuse whatever the user gave you** when reporting conflicts — names if they gave names, item
  numbers if they gave item numbers. Do not run extra lookups to pretty-print.
* **Re-verify after any fix** by calling pc-builder again with the updated set.

## Out of scope

* Building a new PC from scratch when the user has not picked specific parts. Tell them this skill
  is for verifying parts they already have in mind, and answer their build-recommendation question
  normally without this skill.
* Recommending parts based on price / performance opinions when the user only asked about
  compatibility. Stay focused on the compatibility question.
* Inventing compatibility rules pc-builder did not return. If the MCP says valid, do not add fake
  caveats; if invalid, do not expand on reasons it did not give.

## Common pitfalls

* **Doing extra lookups to translate item numbers into names** when the user already gave you
  item numbers and will recognize them. Wasteful and slow — just report what the user gave you.
* **Translating only `reason` and ignoring `reasonTraces`** — the user loses information about
  every failed rule.
* **Using the long-form item number** (`N82E16819113938`). pc-builder expects the short form.
* **Skipping pc-builder for "obvious" cases** like AMD CPU + Intel motherboard. The whole point of
  the skill is that the verdict comes from the MCP, not from you.
* **Suggesting a fix without re-verifying** — every proposed swap must go through pc-builder again
  before being presented as a solution.
* **Silently substituting a part when product-search returns 0 results.** If Newegg does not have
  the exact part the user asked about, you must tell the user and ask — not quietly proceed with
  a similar part. The final verdict must always be about the parts the user actually asked about.
* **Omitting the PSU wattage disclosure** when reporting an `isCompatible: true` build that
  includes a PSU. pc-builder does not check that the PSU is big enough for the GPU; tell the user
  that explicitly instead of letting them assume the green check covers it.
* **Reaching straight for the generic PSU disclaimer text when `newegg-psu-calculator` is actually
  available.** Call it first — a precise "you need ~750W, you have 650W" beats a vague warning.
* **Presenting a checked or replacement item without its Newegg link.** The user should never have
  to go search for a part you already identified by item number.
* **Putting the link in its own column/line instead of hyperlinking the item name.** A redundant
  raw URL next to the name it belongs to is noise — link the name itself.
* **Making up a price, or reusing a stale one, instead of the `Price.FinalPrice` from the
  product-search call you already made for that item.**

## Edge cases

* **HTTP error or curl failure**: Report status code and body. Do not retry silently and do not
  fall back to your own compatibility knowledge.
* **`result.error` in response**: Display `error.message` to the user.
* **`incompatibleItems` empty but `isCompatible: false`**: Treat as an upstream bug — tell the
  user the service returned an inconsistent response and ask them to retry.
* **`incompatibleItems` pairs the same `itemNumber` with multiple `relatedItemNumber`s**: Report
  each pair separately; do not collapse them.
* **A user-supplied item number does not exactly match any product-search result**: treat as not
  found — same handling as a zero-result name search. Do not call pc-builder with an unverified
  item number and do not report whatever `isCompatible` it returns as trustworthy.
