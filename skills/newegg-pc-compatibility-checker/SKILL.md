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

| Purpose | Endpoint |
| --- | --- |
| Compatibility check | `https://apis.newegg.com/ex-mcp/endpoint/ext-pc-builder` |
| Product search | `https://apis.newegg.com/ex-mcp/endpoint/product-search` |

product-search is only needed when the user gives you a model name without an item number —
it resolves `name → ItemNumber`. When the user already gave item numbers, go straight to
pc-builder.

## The flow

### Step 1 — Get every part as an item number

Look at what the user provided:

* **They gave item numbers** (e.g. `19-113-938`) → use them directly and **skip straight to Step
  2**. No lookup needed. Always use the **short hyphenated format** (`19-113-938`), never the
  long URL form (`N82E16819113938`).
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

**If `isCompatible: true`:** Say so plainly, list what was checked, and stop. Do not invent
caveats from your own knowledge.

**Exception — PSU wattage disclosure.** pc-builder's rules cover sockets, chipsets, memory type,
physical fit, and electrical interfaces — but they **do not validate that a PSU's wattage meets
the GPU manufacturer's recommended minimum**. So a 750W PSU paired with an RTX 5090 will return
`isCompatible: true` even though Nvidia recommends 1000W.

Whenever a PSU is among the checked items AND `isCompatible: true`, append one neutral line to
the report:

> ⚠️ pc-builder does not verify PSU recommended wattage against the GPU's requirements. Please
> cross-check your PSU against your GPU manufacturer's official wattage recommendation before
> assembling.

This is not "adding a caveat from your own knowledge" — it is a known, documented limitation of
the MCP, and the user needs to know the compatibility engine's scope.

**If `isCompatible: false`:** Walk through `incompatibleItems[]` one entry at a time. For each
entry:

1. Refer to the two conflicting items using **whatever the user gave you in their original
   question**:
   * User gave model names → use those names (e.g. "Ryzen 9 9950X3D ↔ ASUS B760M-AYW").
   * User gave bare item numbers → use the item numbers (e.g. "19-113-938 ↔ 13-144-674").
   * User gave a mix → use names where they gave names, item numbers where they gave item
     numbers. Do not do a lookup just to pretty-print.
2. List **every** entry in `reasonTraces` — not just `reason`. Each trace is a separate failed
   rule and the user deserves to see all of them.
3. Translate each `reasonTrace` into the user's language (per the top-level "Reply in the user's
   language" rule), with the original English string in parentheses for reference. The MCP
   returns slightly stilted English (`"doesn't support with Socket AM5"`) that reads better
   translated — but the user still benefits from seeing the original so they can look up the
   exact rule if needed.

### Step 4 — Suggest a fix and re-verify

After explaining the conflict, propose a concrete fix:

* Socket / chipset / DDR-generation mismatch → swap the smaller/cheaper side (usually the
  motherboard or RAM, not the CPU).
* PSU undersized vs GPU → suggest a specific replacement PSU.
* Physical fit (case clearance, cooler height) → swap a part of the same category.

Use **product-search** to find the replacement part, then **call pc-builder again** with the
updated item list to verify. Do not declare the fix valid from your own reasoning — re-run
pc-builder. Iterate until `isCompatible: true` or the user changes scope.

## Response format

Use this structure when reporting the verdict to the user:

**Compatible:**

```
## Compatibility check: ✅ Compatible

Checked:
- <user's name for item 1> (<item number>)
- <user's name for item 2> (<item number>)
- ...

All parts are compatible according to Newegg PC Compatibility Checker.
```

**Incompatible:**

```
## Compatibility check: ❌ Incompatible

**Conflict 1: <name1> ↔ <name2>**
- <reasonTraces[0]>
- <reasonTraces[1]>
- ...

**Conflict 2: ...**

### Suggested fix
<specific replacement part with item number>

### Re-verification
[call pc-builder again → report new isCompatible]
```

All headings, labels, and explanations in the response template above must be translated into
the user's language. The English text shown in the template is a structural placeholder — do not
ship English section headers (`## Compatibility check`, `### Suggested fix`, etc.) to a
non-English-speaking user.

## Hard rules

* **Item numbers go to pc-builder in short hyphenated format** (`19-113-938`), not the long form
  (`N82E16819113938`).
* **Never claim compatibility without an `isCompatible: true`** from pc-builder. No verdicts
  derived from your own knowledge. Ever.
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
* **Omitting the PSU wattage disclaimer** when reporting an `isCompatible: true` build that
  includes a PSU. pc-builder does not check that the PSU is big enough for the GPU; tell the user
  that explicitly instead of letting them assume the green check covers it.

## Edge cases

* **HTTP error or curl failure**: Report status code and body. Do not retry silently and do not
  fall back to your own compatibility knowledge.
* **`result.error` in response**: Display `error.message` to the user.
* **`incompatibleItems` empty but `isCompatible: false`**: Treat as an upstream bug — tell the
  user the service returned an inconsistent response and ask them to retry.
* **`incompatibleItems` pairs the same `itemNumber` with multiple `relatedItemNumber`s**: Report
  each pair separately; do not collapse them.
