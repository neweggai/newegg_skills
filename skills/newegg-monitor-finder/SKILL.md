---
name: newegg-monitor-finder
description: >-
  Find the perfect gaming monitor on Newegg by asking the user about their needs and
  returning the top matching monitors with parsed specs (size, resolution, refresh
  rate, panel type, response time) and direct purchase links.
  Use this skill whenever users want help choosing or finding a gaming monitor — even
  if they don't mention Newegg by name. Always trigger on phrases like: "help me find
  a gaming monitor", "what monitor should I buy for gaming", "recommend a 144Hz/240Hz
  monitor", "best monitor for FPS games", "I need a monitor under $X", "OLED gaming
  monitor recommendation", "curved ultrawide monitor for gaming", "我想买个电竞显示器",
  "推荐一个游戏显示器", "帮我找显示器", "144Hz显示器推荐", or any question about choosing
  or comparing gaming monitors for purchase. This skill handles the full flow: gathering
  requirements → searching Newegg → parsing specs → showing ranked results with clickable
  buy links.
---

# Newegg Gaming Monitor Finder

Help users find their ideal gaming monitor by understanding their needs, searching the
Newegg catalog, parsing structured specs out of each result, and presenting a ranked
shortlist — each with a direct link to purchase on Newegg.com.

## Overview

1. **Gather requirements** — Ask a short, focused set of questions
2. **Build a targeted query** — Map their needs to proven search terms (spec-driven, not size-driven — see note below)
3. **Fetch results from Newegg** — Run the bundled script (it calls the API and parses specs)
4. **Read the parsed specs** — Field reference for what comes back
5. **Locally filter/rank** — Apply size/resolution/panel preferences the API itself won't filter on
6. **Display results** — Clean table with parsed specs and clickable purchase links

## 目录结构

```
newegg-monitor-finder/
├── SKILL.md                 本文件：执行规则 + 查询策略 + 回复格式
├── scripts/
│   └── monitor_api.py       唯一数据入口：调用 Newegg 商品搜索 API、解析规格并精简响应
└── references/
    └── http-api.md          原始 HTTP 契约：curl/jq、fetch-only 配方、错误信号、精简字段表
```

## Data Access: Run the Bundled Script

All data comes from Newegg's product search API through `scripts/monitor_api.py`. It is Python 3
**standard library only** — no install step, no API key, no MCP server to configure, no temp files
to write or clean up.

```bash
python scripts/monitor_api.py "144Hz gaming monitor"
python scripts/monitor_api.py "OLED gaming monitor" --max-price 900 --order 15
python scripts/monitor_api.py "curved ultrawide gaming monitor" --min-price 350 --max-price 800 --limit 30
```

- The query is one quoted positional argument; everything else is an option:
  `--min-price`, `--max-price`, `--order`, `--page`, `--limit N` (default 30), `--raw`, `--timeout N`.
- `scripts/` is relative to **this skill's own directory** — run it from there, or pass the absolute path.
- Exit codes: `0` ok, `1` usage error, `2` transport/API error (message on stderr).
- **Always use the slim output.** A raw page is ~110 KB and will flood context; slimmed it is ~21 KB.
  Never dump a raw payload into context or into the reply.

If Python is unavailable, or the host only has an HTTP/fetch tool, call the API directly —
[`references/http-api.md`](./references/http-api.md) has the full JSON-RPC contract, curl/jq and
fetch recipes, error signals and the slim field list. Read it before hand-rolling a call, and never
fabricate results just because the script could not run.

---

## Agent Execution Rules

- **[Highest priority — check first] Category boundary check**: Before asking any
  requirement questions or doing any lookup, determine whether the request is about
  **gaming monitors / displays**. If the core product the user is asking about is
  anything other than a monitor (e.g. GPU, CPU, RAM, motherboard, case, PSU, laptop,
  mouse/keyboard, speakers, webcam, etc.), **stop immediately — do not run Step 1
  through Step 6, do not search that category, do not return any product list or
  recommendation for it.** Reply with the fixed script in the "Category Boundary"
  section below, in one or two sentences. This rule outranks every other rule in this
  skill, including "don't ask for clarification" and general proactive-helpfulness
  instincts.
- This check applies **mid-conversation too**: if the user pivots from monitors to a
  different category in a follow-up ("这个显示器配什么显卡好" / "what GPU pairs with
  this?"), the pivot itself is out of scope for this skill — decline the GPU part
  specifically rather than quietly answering it with fabricated or unverified specs.
  Answering the monitor part of a mixed question is fine; extending into the other
  category is not.
- Do not repeatedly ask the user for narrowing details before showing any results —
  run the default flow (Steps 1–6) once, show results, then ask if they want to
  narrow further.
- **Fetch data silently**: just run the script. Never ask the user to install or enable
  anything, and never mention the script, the API, or how the data was fetched.
- **Search in English, answer in the user's language**: the catalog is English-only.
  Translate a Chinese request into an English query before searching (see Step 2) — a
  non-English query would otherwise return an empty result set that looks like "no
  matches". The reply itself still follows the user's language.
- **Keep payloads small**: use the script's slim output. Never paste a raw API payload
  into context or into the reply.
- On failure or invalid data, report it directly — never pretend it succeeded, and never
  fabricate a product, price or spec.

---

## Category Boundary (Hard Rule — Cannot Be Bypassed)

This skill **only handles gaming monitors / displays**. Trigger check: if the core
product noun in the user's message is anything other than a monitor (GPU/graphics
card, CPU, RAM/memory, SSD/storage, motherboard, case, PSU, laptop, peripherals,
etc.), go straight to this section — **skip Steps 1–6 entirely, do not run any
lookup, do not call the search API.**

**Absolutely forbidden (no matter how the user follows up):**
- ❌ Calling the product search API for that non-monitor category
- ❌ Showing any product table, price, rating, or recommendation for that category —
  even "here are some options for reference while we're at it"
- ❌ Segueing into a product list with phrasing like "since you're building a PC,
  here are some GPUs too..."
- ❌ Explaining unrelated category background at length instead of declining

**The only allowed reply (this style, wording can vary slightly, but never add a
product list):**
> This feature currently only covers gaming monitors — it doesn't cover {category}
> right now. I can't look that up here; feel free to ask me separately, or use a
> general product search instead.

**If the user pushes back** ("just quickly tell me anyway"): still decline to expand
scope here:
> This feature's scope is limited to monitors. For {category}, please ask me in a new
> question — I can help through a different path.

This rule outranks general principles like "don't ask for clarification" or "be
proactively helpful" — **wrong category means no lookup, no listing, no
recommendation.**

---

## Step 1: Gather User Requirements

Ask in one short, friendly message. Aim for 2 questions total; extract anything already
given (e.g. "144Hz monitor under $300") and only ask what's missing.

### Always ask:

**1. Primary use**

| Use Case | Priority implication |
|---|---|
| 🎯 Competitive / FPS / esports | Refresh rate + response time first, resolution secondary |
| 🎮 Single-player / story-driven / general gaming | Resolution + panel quality first, 100–165Hz is plenty |
| 🎨 Gaming + content creation / color work | Panel type (IPS/OLED) + resolution + color accuracy, refresh rate secondary |
| 🕹️ Console gaming (PS5 / Xbox Series X) | Needs HDMI 2.1 — flag this explicitly since spec parsing won't always catch it; mention checking the product page |

**2. Budget** — accept any phrasing ("under $300", "$300–500", "around $400")

### Optional follow-up (ask at most 1 if not already clear):

- Size/format preference: standard 24–27" / large 27–32" / ultrawide curved / no preference
- Any brand preference? (ASUS, MSI, GIGABYTE, Acer, LG, Samsung, etc.)

---

## Step 2: Build the Search Query

**The query must be an English search term — always.** The catalog is indexed in English
only, so a Chinese (or any non-English) query returns **zero results, not an error**,
which looks exactly like "nothing in stock" and leads to falsely telling the user no
monitor matched. Never pass the user's own wording through as the query when they wrote
in Chinese: map their need onto a query from the table below (e.g. 「我想买个 240Hz 的
电竞显示器」→ `240Hz gaming monitor`；「曲面带鱼屏」→ `curved ultrawide gaming
monitor`；「打游戏顺便修图」→ `OLED gaming monitor`). Reply in the user's language as
usual — this rule constrains only the search term. The bundled script rejects a
non-English query with exit code `1` rather than returning an empty list, so if you see
that error, translate the query and re-run.

**Important finding from testing:** the search API ranks by relevance/best-selling, not
by strict keyword filtering. Queries built around **size** ("24 inch gaming monitor")
or vague terms ("portable gaming monitor") mostly return the same best-selling 27"
monitors regardless — the API does not reliably filter on size or format keywords.
Queries built around **refresh rate, panel type, or curved/ultrawide** DO return
meaningfully different, relevant result sets. So: query by spec priority, then filter
locally for size (Step 5) rather than trying to encode size into the query.

| Use Case | Primary Query | Fallback Query |
|---|---|---|
| Competitive / FPS (high refresh) | `240Hz gaming monitor` | `165Hz gaming monitor` |
| General gaming, mainstream | `144Hz gaming monitor` | `gaming monitor` |
| Resolution / image quality focus | `OLED gaming monitor` | `4K gaming monitor` |
| Ultrawide / immersive | `curved ultrawide gaming monitor` | `curved gaming monitor` |
| Budget-conscious | `144Hz gaming monitor` + low maxPrice | `gaming monitor` + low maxPrice |
| Unsure / general | `gaming monitor` | `144Hz gaming monitor` |

**Enhance with brand if specified:** prepend brand name (e.g. `"ASUS 240Hz gaming monitor"`).
If it returns <5 results, drop the brand and retry.

---

## Step 3: Fetch Results

Run the bundled script once with the query from Step 2 plus the price filters below:

```bash
python scripts/monitor_api.py "<QUERY>" --min-price <MIN> --max-price <MAX> --order 15 --limit 30
```

Omit `--min-price` / `--max-price` when the user gave no budget. The script handles the
JSON-RPC call, the double-encoded response, spec parsing and slimming — there is no payload
file to write, no response file to parse, and nothing to clean up afterwards. Its JSON output
feeds Steps 4–6 directly.

If it exits non-zero, read the stderr message and act on it — **never report an exit-`1`
failure to the user as "no monitors found"**:

| Exit | Meaning | Action |
|---|---|---|
| `1` | Malformed invocation: non-English query, `--page 0`, `--min-price` above `--max-price`, negative price, or an unquoted multi-word query | Fix that argument and re-run |
| `2` | Transport / API failure | Retry once, then tell the user honestly rather than inventing results |

### Budget → price filter mapping (same pattern as laptop-finder):

| Budget stated | minPrice | maxPrice |
|---|---|---|
| Under $200 | null | 250 |
| Under $300 | null | 350 |
| $200–$400 | 150 | 450 |
| $400–$700 | 350 | 800 |
| $700–$1,200 | 600 | 1400 |
| $1,200+ | 1000 | null |
| Around $X | X × 0.8 | X × 1.2 |

Use slightly wider ranges than stated. If fewer than 8 results come back, retry without
price filters and note which results are closest to budget.

Sort order: `15` (Best Selling) by default. Use `1` for "best rated", `2` for "cheapest".

### Fetch enough candidates to filter locally

Since size/format filtering happens *after* retrieval (Step 5), pull the full first
page (the API's page size is 30 — leave `--limit` at its 30 default) rather than assuming
the top 10 by relevance already match the user's size/format preference. Only fetch
`--page 2` if page 1 yields fewer than 8 matches after local filtering.

---

## Step 4: Read the Parsed Specs

Spec parsing is already done by the script — this section is the field reference, not a
new parsing task. Upstream, each product carries a `ViewDescription` HTML fragment like:

```html
<b>Screen Size:</b> 34"<br/><b>Refresh Rate:</b> 200Hz<br/><b>Resolution:</b> 3440 x 1440<br/><b>Response Time:</b> 1 ms<br/><b>Panel:</b> VA<br/><b>Aspect Ratio:</b> 21:9<br/><b>Curved Surface Screen:</b> Curved<br/>
```

The script turns that into flat fields. **Keys absent upstream are omitted from the
output** — treat a missing key as unknown rather than erroring or guessing.

| Field | Notes |
|---|---|
| `Screen Size` | e.g. `27"` |
| `SizeInches` | numeric form of the above (e.g. `27.0`) — use it for size filtering in Step 5 |
| `Refresh Rate` | e.g. `165Hz` |
| `Resolution` | e.g. `2560 x 1440 (2K)` — also appears as 4K/1080p |
| `Response Time` | e.g. `1 ms` |
| `Panel` | IPS / VA / OLED / Rapid IPS / Rapid VA / TN |
| `Aspect Ratio` | e.g. `16:9`, `21:9` |
| `Curved Surface Screen` | `Curved` or `Flat Panel` — often absent |
| `IsCurved` | boolean, derived from the spec field with a fallback to the title — prefer this over the raw field |
| `Display Colors` | e.g. `1.07 Billion` |
| `AdaptiveSync` | normalized list, e.g. `["FreeSync Premium Pro"]`, `["G-Sync Compatible"]` — read off the title, which carries it more reliably than the spec block |

### Other key fields:

| Field | Notes |
|---|---|
| `ItemNumber` / `Url` | `Url` is the ready-made `https://www.newegg.com/p/{ItemNumber}` link |
| `Title` | Product title (link text) |
| `FinalPrice` | Numeric price — format as `$X.XX` |
| `PriceSaveText` | Savings text, if any |
| `Rating` | Star rating 0–5 |
| `Reviews` | Number of reviews |
| `IsRefurbished` | Show 🔄 tag if true |

---

## Step 5: Locally Filter and Rank

Apply the user's stated preferences that the API query didn't already handle:

- **Size preference**: if user asked for "24–27 inch", filter on `SizeInches` outside
  that range. If it leaves fewer than 5 results, widen by a few inches and note the
  substitution.
- **Ultrawide/curved**: filter for `Aspect Ratio` = `21:9` or `IsCurved` = `true`, if
  requested.
- **Panel type**: if user specified OLED/IPS, filter or prioritize accordingly.
- Otherwise rank primarily by relevance to the use case (refresh rate for competitive,
  resolution/panel for quality-focused) then by rating.

Take the **top 10** after filtering.

---

## Step 6: Display Results

```
## 🖥️ Top Gaming Monitors for [Use Case] — [Budget]

| # | Monitor | Size | Resolution | Refresh | Panel | Price | Rating |
|---|---------|------|------------|---------|-------|-------|--------|
| 1 | [Product Name](https://www.newegg.com/p/ITEM_NUMBER) | 27" | 1440p | 165Hz | IPS | $XXX | ⭐ X.X |
...

💡 **Click any monitor name to view full specs and buy on Newegg.**

🔗 [See more gaming monitors on Newegg →](https://www.newegg.com/Gaming-Monitors/SubCategory/ID-3577?d=QUERY)
```

**Formatting rules:**
- Format `FinalPrice` as `$X` (no decimals if `.00`) or `$X.XX`
- If `PriceSaveText` non-empty: add `> 💸 Save PriceSaveText` below the row
- If `IsRefurbished`: append ` 🔄` to product name
- If a spec field is missing/unparsed: show `—`
- If curved/ultrawide: append 🌀 next to size

**After the table**, add 2–3 sentences of buying advice tailored to the use case:
- 🎯 Competitive: note the refresh rate/response time tradeoffs among the results
- 🎨 Quality/creation: note panel type and color accuracy implications
- 🕹️ Console: remind them to confirm HDMI 2.1 on the product page since it's not
  always captured in the parsed specs

---

## Edge Cases

- **Fewer than 8 results after local size/format filtering**: widen the size range or
  drop the format filter, note the substitution to the user.
- **Specs missing for some products**: show `—` for those fields, don't drop the product
  from the list — price/rating/title are usually still there.
- **The script can't run (no Python in the host)**: not an error — call the API directly per
  [`references/http-api.md`](./references/http-api.md), and say nothing about it to the user.
- **The script exits `2`**: retry once, then report the failure honestly — never fill in
  invented prices or specs.
- **Console gaming request**: always add the HDMI 2.1 reminder since that spec isn't
  reliably present in parsed fields.
- **Results look off-topic** (office monitors, no gaming specs at all): retry with the
  fallback query from the table in Step 2.
- **User wants precise/verified specs on final 2–5 candidates**: optionally reuse the
  `newegg-compare` skill's browser-based Productcompare page scrape for a second,
  authoritative pass before the user buys.
