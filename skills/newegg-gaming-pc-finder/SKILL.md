---
name: newegg-gaming-pc-finder
description: Recommend prebuilt gaming PCs (desktops and laptops) on Newegg by the games the user
  wants to play, target resolution, and budget — powered by Newegg's official Gaming PC Finder
  engine. Returns real per-game FPS, performance tier and percentile, VR-ready status, CPU/GPU,
  price and purchase links. This covers prebuilt gaming SYSTEMS only, not individual components
  or custom part-by-part builds. Trigger phrases include "gaming pc finder", "recommend a gaming
  pc", "gaming desktop for a game", "best pc to play a game at 4k", "gaming pc under $X", "what
  pc runs this game", 游戏主机推荐, 打游戏的电脑, 配一台游戏电脑, 4K玩游戏的主机, 预算内的游戏台式机,
  玩游戏买什么电脑.
---

# Newegg Gaming PC Finder

## Important Background (Read First)

This skill recommends **prebuilt gaming systems** — gaming **desktops** and gaming **laptops** —
sold on Newegg, ranked by Newegg's official **Gaming PC Finder** benchmark engine. For each
system it can show the **real measured FPS** for the games the user cares about, at their target
resolution, plus a performance tier, VR-ready flag, price, rating and a direct purchase link.

It does **not** build a PC part-by-part, price individual components, or check part
compatibility. Those belong to other skills (e.g. a PC Builder / component-search skill).

## 目录结构

```
newegg-gaming-pc-finder/
├── SKILL.md                 本文件：执行规则 + 四个操作的参数契约 + 回复格式
├── scripts/
│   └── pgg_api.py           唯一数据入口：调用 Gaming PC Finder API 并精简响应
└── references/
    └── http-api.md          原始 HTTP 契约：curl/jq、fetch-only 配方、错误信号、精简字段表
```

## Data Access: Run the Bundled Script

All data comes from Newegg's Gaming PC Finder API through `scripts/pgg_api.py`. It is Python 3
**standard library only** — no install step, no API key, no server to configure. There are four
operations:

| Operation | Purpose |
|---|---|
| `game_list` | Dictionary of selectable games + supported resolutions |
| `property_list` | CPU / GPU / brand facet buckets for the selected games |
| `product_recommend` | Curated recommended systems (with per-game FPS) |
| `product_search` | Paginated, filterable system listing (budget / sort / facets) |

```bash
python scripts/pgg_api.py game_list
python scripts/pgg_api.py property_list GameNValues=5171
python scripts/pgg_api.py product_recommend GameNValues=5171 ResolutionNValues=5015 ComputerType=D
python scripts/pgg_api.py product_search GameNValues=5171 ResolutionNValues=5015 ComputerType=D Budget=0-2500 Sort=4 PageIndex=1 PageSize=20 --limit 10
```

- Arguments are `Key=Value` pairs using the exact API argument names documented in Steps 1–3 below.
- `CountryCode=USA` / `CompanyCode=1003` are applied by default; override with `--country` /
  `--company`.
- `--limit N` caps printed items (default 20). `--raw` prints the full upstream payload — only when
  a field outside the slim view is genuinely needed.
- Exit codes: `0` ok, `1` usage error, `2` transport/API error (message on stderr).
- `scripts/` is relative to **this skill's own directory** — run it from there, or pass the
  absolute path.

**Always use the slim output.** A raw `product_search` response is ~230 KB and will flood context;
slimmed, the same call is ~3 KB. Never dump a raw payload into context or into the reply.

If Python is unavailable, or the host only has an HTTP/fetch tool, call the API directly —
[`references/http-api.md`](./references/http-api.md) has the full JSON-RPC contract, curl/jq and
fetch recipes, error signals and the slim field list. Read it before hand-rolling a call, and never
fabricate results just because the script could not run.

## Architecture: The Finder Flow

No operation takes a raw game name; the engine works on numeric **N-values**. So the flow is:

| Step | Operation | Why |
|---|---|---|
| 1 | `game_list` | Resolve the user's game names + resolution into `N` values |
| 2 | `product_recommend` | Get curated builds with real `GameFpsInfos` |
| 3 (optional) | `product_search` | Apply budget / sort / paging when the user wants more control |
| — (optional) | `property_list` | List available CPU/GPU/brand facets to guide narrowing |

**Fixed rule**: always resolve N-values via Step 1 first; never guess an `N`.

## Agent Execution Rules

- **[Highest priority — check first] Category boundary**: Before any lookup, confirm the request
  is about a **prebuilt gaming PC / desktop / laptop**. If the user wants individual components
  (GPU, CPU, RAM, SSD, motherboard, PSU, monitor, case…), a custom part-by-part build, or any
  non-system category, **stop — run no operation at all, do not show a product list** — and reply
  with the fixed script in the "Category Boundary" section below. This rule outranks every other
  rule, including "don't ask for clarification".
- **Fetch data silently**: just run the script. Never ask the user to install or enable anything,
  and never mention the script, the API, or how the data was fetched.
- **Don't over-question**: gather at most 2–3 essentials (games, resolution, budget), then run
  the default flow and show results. Ask to narrow further only after showing something.
- **Sensible defaults (don't stall on missing info)**:
  - No resolution given → default to **1080p** and say so in the reply (ask only if the user
    clearly signals high-res / 4K ambitions).
  - No budget given → don't apply a price filter; show the curated recommendations first, then
    offer to narrow by budget.
  - Form factor unspecified → default to **desktop** (`ComputerType=D`); switch to laptop
    (`L`) only if the user mentions a laptop / portability.
- **Multiple games (≤4)**: pass all matched game N-values together in one call; the engine
  returns FPS per game. Present each game's FPS (a compact `Game: fps` list, or one FPS column
  per game) plus `UpToFps`. If the user named a priority title, rank/talk to that game's FPS.
- **Filter values must come from the engine (facet grounding)**: to filter by CPU, GPU, or
  brand, first call `property_list` (or read `CpuTypes` / `GpuTypes` / `HotBrands` from a
  `product_search` response) and pass **only** names / N-values that appear there. Never pass a
  free-text CPU/GPU/brand string the user typed without first matching it to a real facet value —
  unmatched values silently return no results.
- **Chinese input**: match the user's spoken game names (including nicknames, e.g. 悟空 →
  "Black Myth: Wukong") against the `GameInfos` dictionary from Step 1 by meaning; translate as
  needed. Never invent an `N` value.
- **Real FPS only**: every FPS number must come from `GameFpsInfos` / `UpToFps`. If the engine
  returns no FPS for a game, leave it blank and say so — never estimate or fabricate frames.
- **Honest labels**: mark refurbished (`Feature.IsRefurbished`), open-box (`Feature.IsOpenBoxed`),
  non-new `Feature.ProductType`, and out-of-stock (`Instock=false`) items truthfully.
- **Keep payloads small**: `product_search` returns a very large response. Use the bundled client's
  slim output (or `jq`-filter it) and never paste a raw payload into context or the reply.
- On failure or invalid data, report it directly — never pretend it succeeded. Retry a failed call
  at most once (see `references/http-api.md` if the script itself cannot run) before reporting.

## Step 1: Resolve Games & Resolution

Run `game_list` with:

| Argument | Type | Required | Description |
|---|---|---|---|
| `CountryCode` | string | Yes | `USA` (default) or `CAN` |
| `CompanyCode` | integer | Yes | Default `1003` |

Response (the script returns this slimmed as `Games` / `Resolutions`):
- `GameInfos[]` → `{ N, Name, Id }` — match the user's games to `N` (max 4 games).
- `ResolutionInfos[]` → `{ N, Group, Name }` — e.g. `1080P=5013`, `1440P=5012`, `4K=5015`
  (use the live values, don't hardcode).

If a requested game isn't in the dictionary, show the user the supported games and ask them to
pick from those.

## Step 2: Get Recommendations

Run `product_recommend` with:

| Argument | Type | Required | Description |
|---|---|---|---|
| `GameNValues` | string | Yes | Space-separated game `N` values, **≤4** |
| `ResolutionNValues` | string | Yes | A single resolution `N` value |
| `ComputerType` | string | No | `D` = desktop, `L` = laptop |
| `CpuTypeNames` | string | No | Space-separated CPU type names (≤25 chars each) — **must be real facet values from `property_list`**, not free text |
| `GpuTypeNames` | string | No | Space-separated GPU type names — **from `property_list`** |
| `BrandNValues` | string | No | Space-separated brand `N` values — **from `property_list` `HotBrands`** |
| `CountryCode` / `CompanyCode` | | Yes | As Step 1 |

> Only pass `CpuTypeNames` / `GpuTypeNames` / `BrandNValues` after grounding them in
> `property_list` output (see the facet-grounding rule above). For a plain "recommend me a PC to
> play X at Y", omit all three and let the engine rank.

Response → `RecommendItems[]`, key fields per item:
- `Description.Title` / `Description.WebDescription` — title (link text)
- `Item` — build purchase URL: `https://www.newegg.com/p/{Item}`
- `Cpu`, `Gpu`, `FinalPrice`
- `GameFpsInfos[]` → `{ Name, Fps }` — **real per-game FPS**; `UpToFps`; `VrReady`
- `Score` — **Spy Score** (3DMark Time Spy benchmark, higher = stronger; e.g. 25706)
- `Level`, `PerformancePercentile` — performance tier (MAINSTREAM/ENTHUSIAST/…) / percentile
- `Review.RatingOneDecimal` (0–5), `Review.HumanRating` (review count)
- `Feature.IsRefurbished` / `Feature.IsOpenBoxed` / `Feature.ProductType`, `Instock`

## Step 3 (optional): Budget / Sort / More Results

When the user gives a budget, wants the cheapest / highest-performance, or wants more than the
curated set, run `product_search`:

| Argument | Type | Required | Description |
|---|---|---|---|
| `PageIndex` | integer | Yes | **1-based** page index — start at `1`. (The published schema mislabels it "zero-based", but `PageIndex:0` returns an empty `Items` list; always pass `1` for the first page.) |
| `PageSize` | integer | Yes | Items per page (default 20, max 100) |
| `GameNValues` / `ResolutionNValues` | string | Yes | From Step 1 |
| `Budget` | string | No | `{min}-{max}` budget range |
| `Price` | string | No | `{min}-{max}` navigation price range |
| `Sort` | integer | No | `1`=Best Deals, `2`=Lowest Price, `3`=Highest Price, `4`=Highest Performance |
| `CpuTypeNames` / `GpuTypeNames` / `BrandNValues` / `ComputerType` | string | No | Same semantics as Step 2 |
| `CountryCode` / `CompanyCode` | | Yes | As Step 1 |

Response → `Items[]` (each with a scalar `Fps` for the selected game, price, review, feature flags
like Step 2), plus `NumberOfItems`, `Budget` range metadata, `SortOption`, and
`CpuTypes`/`GpuTypes`/`HotBrands` facets. To surface available CPU/GPU/brand choices for narrowing,
`property_list` (args: `GameNValues`, `CountryCode`, `CompanyCode`) returns the same facet buckets —
note `CpuTypes`/`GpuTypes` are vendor buckets (e.g. `Intel`, `AMD`), not model names.

This is the largest response in the flow — slim it before reading (bundled client, or `jq`).

## Worked Example (End-to-End)

**User:** “想配一台 4K 玩黑神话悟空的游戏台式机，预算 2500 左右”

1. **Boundary check** → prebuilt gaming desktop → proceed. Essentials present (game, 4K,
   ~$2500 desktop); no need to ask more.
2. **Step 1** — `python scripts/pgg_api.py game_list` → match 悟空 → `Black Myth: Wukong`
   (`N=5171`); 4K → `N=5015`.
3. **Step 2 — `product_recommend`** (`GameNValues:"5171", ResolutionNValues:"5015",
   ComputerType:"D", CountryCode:"USA", CompanyCode:1003`) → curated builds with per-game FPS.
   (No CPU/GPU/brand filter passed — user didn't specify, so let the engine rank.)
4. **Step 3 — `product_search`** (because a budget was given) (`PageIndex:1, PageSize:20,
   GameNValues:"5171", ResolutionNValues:"5015", ComputerType:"D", Budget:"0-2500", Sort:4,
   CountryCode:"USA", CompanyCode:1003`) → filter to ≤$2500, sorted by highest performance.
5. **Reply** — merge/rank, keep top ~5, render the table:

```
## 🎮 Gaming PCs for Black Myth: Wukong @ 4K

| # | System | Price | CPU / GPU | FPS (Wukong) | Spy Score | Performance | Rating |
|---|---|---|---|---|---|---|---|
| 1 | [Skytech O11 Vision](https://www.newegg.com/p/3D5-000Z-003U5) | $1,899.99 | Ryzen 7 7700X / RX 9070 XT | 35 fps | 25,706 | ⭐ Mainstream · Top 7% · 🕶️ VR | ⭐4.0 (1) |
| 2 | [STORMCRAFT Phantom](https://www.newegg.com/p/83-420-035) | $2,499.99 | Ultra 7 265F / RTX 5080 | 50 fps | 28,460 | ⭐ Enthusiast · Top 4% · 🕶️ VR | ⭐4.4 (72) |

💡 4K Wukong is demanding — the RX 9070 XT build lands ~35 fps and leaves budget headroom; the
RTX 5080 build pushes ~50 fps at the top of your budget. "Spy Score" is the 3DMark Time Spy
result (higher = stronger). See the full [Gaming PC Finder](https://www.newegg.com/tools/gaming-pc-finder?cm_sp=aishoppingassistant).
```

> Follow-up "只要 AMD 显卡" → call `property_list` (`GameNValues:"5171"`), find the real GPU
> facet name for the AMD card, then re-run with that `GpuTypeNames` value — never pass a guessed
> string.

## Category Boundary (Hard Rule — Cannot Be Bypassed)

This skill **only handles prebuilt gaming systems** (gaming desktops & laptops). If the core
product noun is anything else — a standalone component (GPU/CPU/RAM/SSD/motherboard/PSU/case/
monitor), a custom part-by-part build, peripherals, or another category — go straight here:
**skip all steps, run no lookup, show no product list.**

**Absolutely forbidden (no matter how the user follows up):**
- ❌ Running any finder operation for that non-system request — `scripts/pgg_api.py`, curl, or
  fetch alike
- ❌ Showing any table, price, FPS, or recommendation for that category
- ❌ Segueing with "but here are some builds anyway…"

**The only allowed reply (wording may vary slightly, never add a product list):**
> This finder only recommends complete prebuilt gaming PCs (desktops & laptops). I can't look
> up {request} here — for that, please try the matching tool (e.g. the PC Builder / component
> search) or ask me in a separate question.

This rule outranks "don't ask for clarification" and "be proactively helpful" — **wrong category
means no lookup, no listing, no recommendation.**

## Customer-Facing Tone Guidelines

Replies must read like a shopping assistant, not a process report.

**Forbidden phrasing (implementation-exposing):** any technical term like "N value / Step 1 /
endpoint / tool / API / script / `product_recommend`", or explaining how results were retrieved.

**Preferred phrasing:** state which systems match and why they fit the user's games/resolution/
budget; if few match, gently offer alternatives ("if you're open to 1440p instead of 4K, this
build hits higher FPS") rather than emphasizing scarcity. Keep it concise and conversational.

## Response Format

```
## 🎮 Gaming PCs for {games} @ {resolution}

| # | System | Price | CPU / GPU | FPS ({game}) | Spy Score | Performance | Rating |
|---|---|---|---|---|---|---|---|
| 1 | [Title](https://www.newegg.com/p/{Item}) | $1,899.99 | Ryzen 7 7700X / RX 9070 XT | 35 fps | 25,706 | ⭐ Mainstream · Top 7% | ⭐4.0 (1) |
| 2 | [Title](...) | ... | ... | ... | ... | ... | ... |

💡 GPU drives your target-resolution frame rate; picks are ranked on real benchmark FPS. "Spy Score" is the 3DMark Time Spy result — a higher number means a stronger system overall.
```

- **No product images**: consuming surfaces gate/block external images, so do **not** embed
  thumbnails. Link the product title only; users open the product page to see photos.
- **Spy Score** column = the item's `Score` (3DMark Time Spy). Format with thousands separators.

- Add badges where relevant: `🕶️ VR Ready`, `🔄 Refurbished`, `📦 Open Box`, `⚠️ Out of stock`.
- Multiple games: show FPS per game (extra columns or a compact `game: fps` list), plus `UpToFps`.
- Close with 2–3 sentences of tailored advice (value pick vs. performance pick), and a link to
  the full [Gaming PC Finder](https://www.newegg.com/tools/gaming-pc-finder?cm_sp=aishoppingassistant)
  for the interactive experience. Follow the site rule: at most 2 links per reply, no repeats.

## Edge Cases

- **No game matched in the dictionary**: show the supported games from Step 1, ask the user to choose.
- **`product_recommend` returns empty**: suggest relaxing constraints (lower resolution, raise
  budget, fewer games) and offer the web tool link — don't fabricate results.
- **A call fails**: retry once, then report it honestly; never fill in fake prices/FPS.
- **No Python in the host**: not an error — call the API directly per
  ([`references/http-api.md`](./references/http-api.md)) and say nothing about it to the user.
- **Some items missing FPS/price**: keep the row, leave that cell blank, and note it — don't guess.
