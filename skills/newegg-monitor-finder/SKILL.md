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
3. **Fetch results from Newegg** — Call the product search API (cross-platform curl + a tested parsing snippet — see note below)
4. **Parse specs** — Extract structured fields from `ViewDescription`
5. **Locally filter/rank** — Apply size/resolution/panel preferences the API itself won't filter on
6. **Display results** — Clean table with parsed specs and clickable purchase links
7. **Clean up** — Remove temp files created during the search, don't leave scratch scripts behind

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

## Step 3: Call the Newegg Product Search API

The **tool name is `"newegg product search"`** (with spaces).

**Cross-platform note:** don't inline multi-line JSON directly in the `-d` flag — on
Windows PowerShell, `curl` is aliased to `Invoke-WebRequest` (which doesn't understand
`-d`), and even after switching to real `curl.exe`, PowerShell's line-continuation and
quoting rules break bash-style `-d '{...}'` multi-line bodies (mismatched braces,
unmatched quotes). Instead, **write the JSON body to a temp file first, then reference
it with `-d @payload.json`** — this syntax works identically in bash, macOS/Linux
shells, and Windows PowerShell/cmd.

**Step 3a — write the payload to a file in the OS temp directory, never the project
directory.** If this skill is running inside a coding tool (Cursor, Claude Code, etc.)
with a real project open, writing scratch files into the project folder will show up
in `git status` and risks getting committed by accident. Always target:
- **bash / macOS / Linux:** `/tmp/newegg-monitor-payload.json`
- **Windows:** `$env:TEMP\newegg-monitor-payload.json`

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "newegg product search",
    "arguments": {
      "query": "<QUERY>",
      "minPrice": <MIN_OR_NULL>,
      "maxPrice": <MAX_OR_NULL>,
      "order": 15
    }
  }
}
```

**Step 3b — call curl referencing the file:**

- **bash / macOS / Linux:**
  ```bash
  curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/product-search" \
    -H "Content-Type: application/json" \
    -d @/tmp/newegg-monitor-payload.json -o /tmp/newegg-monitor-response.json
  ```
- **Windows (PowerShell or cmd):** use `curl.exe` explicitly — plain `curl` in
  PowerShell is the `Invoke-WebRequest` alias and will fail.
  ```powershell
  curl.exe -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/product-search" -H "Content-Type: application/json" -d "@$env:TEMP\newegg-monitor-payload.json" -o "$env:TEMP\newegg-monitor-response.json"
  ```

Reuse the same payload file for subsequent queries in the same session — just
overwrite its contents before each new call. Always write the response to a file too
(`-o`) rather than only printing it — Step 3c parses it from disk.

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
page (`pageSize` ~30) rather than assuming the top 10 by relevance already match the
user's size/format preference. Only fetch page 2 if page 1 yields fewer than 8
matches after local filtering.

**Step 3c — parse the response. Use the snippet below exactly as given — do not write
a new parsing script from scratch each time.** The response is JSON-RPC wrapping a JSON
*string* (`result.content[0].text`) that itself needs a second parse to reach the
`products` array. This double-encoding is what caused repeated PowerShell syntax
errors in testing (mismatched braces/quotes from ad-hoc regex scripts) — the snippets
below are tested and known to work.

- **bash / macOS / Linux (requires `python3`, already available in this environment):**
  ```bash
  python3 -c "
  import json, re
  with open('/tmp/newegg-monitor-response.json') as f:
      data = json.load(f)
  parsed = json.loads(data['result']['content'][0]['text'])
  print('total:', parsed.get('total'))
  def parse_specs(vd):
      if not vd: return {}
      return {k.strip(): v.strip() for k, v in re.findall(r'<b>(.*?):</b>\s*([^<]*)', vd)}
  for p in parsed['products']:
      specs = parse_specs(p.get('ViewDescription', ''))
      print(p['ItemNumber'], '|', p['WebDescription'], '| \$', p['Price']['FinalPrice'],
            '|', specs.get('Screen Size'), specs.get('Resolution'), specs.get('Refresh Rate'), specs.get('Panel'))
  "
  ```
- **Windows (PowerShell) — no Python required:**
  ```powershell
  $raw = Get-Content -Raw "$env:TEMP\newegg-monitor-response.json" | ConvertFrom-Json
  $parsed = $raw.result.content[0].text | ConvertFrom-Json
  Write-Host "total: $($parsed.total)"
  foreach ($p in $parsed.products) {
      $vd = $p.ViewDescription
      $specs = @{}
      if ($vd) {
          foreach ($m in [regex]::Matches($vd, '<b>(.*?):</b>\s*([^<]*)')) {
              $specs[$m.Groups[1].Value.Trim()] = $m.Groups[2].Value.Trim()
          }
      }
      Write-Host "$($p.ItemNumber) | $($p.WebDescription) | `$$($p.Price.FinalPrice) | $($specs['Screen Size']) $($specs['Resolution']) $($specs['Refresh Rate']) $($specs['Panel'])"
  }
  ```
  This uses `[regex]::Matches` and `$()` subexpressions rather than inline `-match` or
  string concatenation, which is what avoids the quoting/brace ambiguity PowerShell ran
  into previously.

Take the resulting parsed product list forward into Step 4/5. **Do not iterate on your
own version of this script if it errors — re-copy the snippet above exactly** rather
than hand-editing it live; most failures come from small edits (added line breaks,
re-typed quotes) introduced while debugging.

---

## Step 4: Parse Specs from Each Product

This step is already handled by the Step 3c snippet — this section is the field
reference, not a new parsing task. Each product includes a `ViewDescription` field —
an HTML fragment with labeled specs. Example:

```html
<b>Screen Size:</b> 34"<br/><b>Refresh Rate:</b> 200Hz<br/><b>Resolution:</b> 3440 x 1440<br/><b>Response Time:</b> 1 ms<br/><b>Panel:</b> VA<br/><b>Aspect Ratio:</b> 21:9<br/><b>Curved Surface Screen:</b> Curved<br/>
```

Parse each `<b>Label:</b> Value` pair into a dict. Fields observed (not all present on
every product — parse defensively, treat missing as unknown rather than erroring):

| Label | Notes |
|---|---|
| `Screen Size` | e.g. `27"` |
| `Refresh Rate` | e.g. `165Hz` |
| `Resolution` | e.g. `2560 x 1440 (2K)` — also appears as 4K/1080p |
| `Response Time` | e.g. `1 ms` |
| `Panel` | IPS / VA / OLED / Rapid IPS / Rapid VA / TN |
| `Aspect Ratio` | e.g. `16:9`, `21:9` |
| `Curved Surface Screen` | `Curved` or `Flat Panel` — not always present |
| `Display Colors` | e.g. `1.07 Billion` |

Also check `WebDescription` (title) for G-Sync/FreeSync mentions — this is more
reliably present there than in `ViewDescription`.

### Other key fields (same as other finder skills):

| Field | Notes |
|---|---|
| `ItemNumber` | Build URL: `https://www.newegg.com/p/{ItemNumber}` |
| `WebDescription` | Product title |
| `Price.FinalPrice` | Numeric price — format as `$X.XX` |
| `Price.PriceSaveText` | Savings text, if any |
| `Price.RatingOneDecimal` | Star rating 0–5 |
| `Price.HumanRating` | Number of reviews |
| `IsRefurbished` | Show 🔄 tag if true |

---

## Step 5: Locally Filter and Rank

Apply the user's stated preferences that the API query didn't already handle:

- **Size preference**: if user asked for "24–27 inch", filter out parsed `Screen Size`
  outside that range. If it leaves fewer than 5 results, widen by a few inches and note
  the substitution.
- **Ultrawide/curved**: filter for `Aspect Ratio` = `21:9` or `Curved Surface Screen` =
  `Curved`, if requested.
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

## Step 7: Clean Up Temp Files

After displaying the final results (Step 6), delete the temp files created in Step 3:

- **bash / macOS / Linux:** `rm -f /tmp/newegg-monitor-payload.json /tmp/newegg-monitor-response.json`
- **Windows (PowerShell):** `Remove-Item "$env:TEMP\newegg-monitor-payload.json", "$env:TEMP\newegg-monitor-response.json" -ErrorAction SilentlyContinue`

Don't leave scratch scripts or intermediate JSON files behind in the project directory
or visible chat history — if the host tool surfaces every shell command as a visible
step (as some agentic coding tools do), keeping the file count and step count minimal
also keeps what the end customer sees clean. Reuse and overwrite the same two temp
files across retries within one session rather than creating new numbered files
(`payload2.json`, `parse_v2.ps1`, etc.) — this alone eliminates most of the file
clutter seen in earlier testing.

---

## Edge Cases

- **Fewer than 8 results after local size/format filtering**: widen the size range or
  drop the format filter, note the substitution to the user.
- **`ViewDescription` missing or unparseable for some products**: skip those spec
  fields (show `—`), don't drop the product from the list — price/rating/title are
  usually still there.
- **Console gaming request**: always add the HDMI 2.1 reminder since that spec isn't
  reliably present in parsed fields.
- **Results look off-topic** (office monitors, no gaming specs at all): retry with the
  fallback query from the table in Step 2.
- **User wants precise/verified specs on final 2–5 candidates**: optionally reuse the
  `newegg-compare` skill's browser-based Productcompare page scrape for a second,
  authoritative pass before the user buys.
