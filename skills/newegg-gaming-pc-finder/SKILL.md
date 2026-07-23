---
name: newegg-gaming-pc-finder
license: MIT
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

Help users find a **prebuilt gaming system** — a gaming **desktop** or **laptop** — on Newegg,
ranked by Newegg's official **Gaming PC Finder** benchmark engine. For each system you can show
the **real measured FPS** for the games the user cares about at their target resolution, plus a
performance tier, VR-ready flag, price, rating and a direct purchase link.

This skill covers complete prebuilt gaming systems only. It does **not** build a PC part-by-part,
price individual components, or check part compatibility — those belong to other skills.

## Overview

1. **Gather requirements** — games, target resolution, budget (2–3 questions max)
2. **Resolve to N-values** — the engine keys off numeric game/resolution IDs, not raw names
3. **Get recommendations** — curated builds with real per-game FPS
4. **(Optional) Filter** — budget / sort / CPU-GPU-brand narrowing, then show the top results

All data comes from the **`gaming-pc-finder`** MCP endpoint, called with the `bash` tool via
`curl`. The endpoint is stateless — a bare `tools/call` works, no session handshake needed.
Every response wraps its payload as a JSON string in `result.content[0].text` — parse that.

---

## Agent Execution Rules

- **[Highest priority — check first] Category boundary**: only handle **prebuilt gaming systems**
  (gaming desktops & laptops). If the user wants a standalone component (GPU/CPU/RAM/SSD/
  motherboard/PSU/case/monitor), a custom part-by-part build, peripherals, or another category,
  **stop — run no curl, show no product list** — and reply with the fixed script in the
  "Category Boundary" section. This outranks every other rule, including "don't ask for clarification".
- **Don't over-question**: gather at most 2–3 essentials, then run the flow and show results.
- **Sensible defaults (don't stall)**: no resolution → default **1080p** (say so); no budget →
  don't price-filter, show curated picks first; form factor unspecified → **desktop** (`D`).
- **Multiple games (≤4)**: pass all matched game N-values in one call; present FPS per game plus
  `UpToFps`. If the user named a priority title, speak to that game's FPS.
- **Chinese input**: match spoken game names / nicknames (e.g. 悟空 → "Black Myth: Wukong")
  against the Step-1 dictionary by meaning. **Never invent an N-value.**
- **Real FPS only**: every FPS number comes from `GameFpsInfos` / `UpToFps`. If missing, leave
  blank and say so — never estimate frames.
- **Filter values must be grounded**: to filter by CPU/GPU/brand, first pull real facet values
  from Step 4's `property_list` and pass **only** values that appear there — a free-text string
  the user typed will silently return no results.
- **Honest labels**: mark refurbished, open-box, non-new `ProductType`, and out-of-stock truthfully.
- On curl failure or invalid JSON, report the error directly — never pretend it succeeded.

---

## Step 1: Resolve Games & Resolution

```bash
curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/gaming-pc-finder" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {
      "name": "getapi_adapter_Pgg_game_list",
      "arguments": { "CountryCode": "USA", "CompanyCode": 1003 }
    }
  }'
```

Parse `result.content[0].text` as JSON:
- `GameInfos[]` → `{ N, Name, Id }` — match the user's games to `N` (max 4).
- `ResolutionInfos[]` → `{ N, Group, Name }` — e.g. `1080P=5013`, `1440P=5012`, `4K=5015`
  (read the live values, don't hardcode).

If a requested game isn't in the dictionary, show the supported games and ask the user to pick.

---

## Step 2: Get Recommendations

```bash
curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/gaming-pc-finder" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {
      "name": "getapi_adapter_Pgg_product_recommend",
      "arguments": {
        "GameNValues": "5171",
        "ResolutionNValues": "5015",
        "ComputerType": "D",
        "CountryCode": "USA", "CompanyCode": 1003
      }
    }
  }'
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `GameNValues` | **Yes** | Space-separated game N-values, **≤4** |
| `ResolutionNValues` | **Yes** | A single resolution N-value |
| `ComputerType` | No | `D` = desktop, `L` = laptop |
| `CpuTypeNames` / `GpuTypeNames` | No | Space-separated facet names — **only real values from `property_list`** |
| `BrandNValues` | No | Space-separated brand N-values — **from `property_list` `HotBrands`** |
| `CountryCode` / `CompanyCode` | **Yes** | Default `USA` / `1003` |

> For a plain "recommend a PC to play X at Y", omit CPU/GPU/brand and let the engine rank.

### Response → `RecommendItems[]`, key fields
- `Description.Title` — title (link text); `Item` → purchase URL `https://www.newegg.com/p/{Item}`
- `Cpu`, `Gpu`, `FinalPrice`
- `GameFpsInfos[]` → `{ Name, Fps }` — **real per-game FPS**; `UpToFps`; `VrReady`
- `Score` — **Spy Score** (3DMark Time Spy, higher = stronger; e.g. 25706)
- `Level`, `PerformancePercentile` — tier (MAINSTREAM/ENTHUSIAST/…) / percentile
- `Review.RatingOneDecimal` (0–5), `Review.HumanRating` (review count)
- `Feature.IsRefurbished` / `Feature.IsOpenBoxed` / `Feature.ProductType`, `Instock`

---

## Step 3 (optional): Budget / Sort / More Results

Use when the user gives a budget, wants cheapest / highest-performance, or wants more than the
curated set.

```bash
curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/gaming-pc-finder" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {
      "name": "getapi_adapter_Pgg_product_search",
      "arguments": {
        "PageIndex": 1, "PageSize": 20,
        "GameNValues": "5171", "ResolutionNValues": "5015",
        "ComputerType": "D", "Budget": "0-2500", "Sort": 4,
        "CountryCode": "USA", "CompanyCode": 1003
      }
    }
  }'
```

| Argument | Required | Description |
|---|---|---|
| `PageIndex` | **Yes** | **1-based** — start at `1`. (Schema mislabels it "zero-based"; `PageIndex:0` returns empty `Items`.) |
| `PageSize` | **Yes** | Items per page (default 20, max 100) |
| `GameNValues` / `ResolutionNValues` | **Yes** | From Step 1 |
| `Budget` | No | `{min}-{max}` budget range |
| `Price` | No | `{min}-{max}` navigation price range |
| `Sort` | No | `1`=Best Deals, `2`=Lowest Price, `3`=Highest Price, `4`=Highest Performance |
| `CpuTypeNames` / `GpuTypeNames` / `BrandNValues` / `ComputerType` | No | As Step 2 (facet-grounded) |
| `CountryCode` / `CompanyCode` | **Yes** | Default `USA` / `1003` |

Response → `Items[]` (each with `Fps`, price, review, feature flags), `Budget` range metadata,
`SortOption`, and `CpuTypes` / `GpuTypes` / `HotBrands` facets.

---

## Step 4 (optional): Facet values for filtering

Before passing any `CpuTypeNames` / `GpuTypeNames` / `BrandNValues`, get the real facet values:

```bash
curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/gaming-pc-finder" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {
      "name": "getapi_adapter_Pgg_property_list",
      "arguments": { "GameNValues": "5171", "CountryCode": "USA", "CompanyCode": 1003 }
    }
  }'
```

Returns `CpuTypes` / `GpuTypes` (`{ Id, Name }`) and `HotBrands` (`{ N, Name }`). Pass only these
real names / N-values back into Step 2 or Step 3.

---

## Worked Example (End-to-End)

**User:** “想配一台 4K 玩黑神话悟空的游戏台式机，预算 2500 左右”

1. **Boundary check** → prebuilt gaming desktop → proceed. Essentials present; no need to ask more.
2. **Step 1 `game_list`** → 悟空 → `Black Myth: Wukong` (`N=5171`); 4K → `N=5015`.
3. **Step 2 `product_recommend`** (`GameNValues:"5171", ResolutionNValues:"5015", ComputerType:"D"`)
   → curated builds with per-game FPS. No CPU/GPU/brand filter (user didn't specify).
4. **Step 3 `product_search`** (budget given) (`PageIndex:1, PageSize:20, Budget:"0-2500", Sort:4`,
   same game/resolution) → ≤$2500, highest performance first.
5. **Reply** — merge/rank, keep top ~5:

```
## 🎮 Gaming PCs for Black Myth: Wukong @ 4K

| # | System | Price | CPU / GPU | FPS (Wukong) | Spy Score | Performance | Rating |
|---|---|---|---|---|---|---|---|
| 1 | [Skytech O11 Vision](https://www.newegg.com/p/3D5-000Z-003U5) | $1,899.99 | Ryzen 7 7700X / RX 9070 XT | 35 fps | 25,706 | ⭐ Mainstream · Top 7% · 🕶️ VR | ⭐4.0 (1) |
| 2 | [STORMCRAFT Phantom](https://www.newegg.com/p/83-420-035) | $2,499.99 | Ultra 7 265F / RTX 5080 | 50 fps | 28,460 | ⭐ Enthusiast · Top 4% · 🕶️ VR | ⭐4.4 (72) |

💡 4K Wukong is demanding — the RX 9070 XT build lands ~35 fps with budget headroom; the RTX 5080
build pushes ~50 fps near the top of your budget. "Spy Score" is the 3DMark Time Spy result
(higher = stronger). See the full [Gaming PC Finder](https://www.newegg.com/tools/gaming-pc-finder?cm_sp=aishoppingassistant).
```

> Follow-up "只要 AMD 显卡" → Step 4 `property_list`, find the real AMD GPU facet name, then
> re-run Step 2/3 with that `GpuTypeNames` value — never pass a guessed string.

---

## Category Boundary (Hard Rule — Cannot Be Bypassed)

This skill **only handles prebuilt gaming systems**. If the core product noun is anything else —
a standalone component (GPU/CPU/RAM/SSD/motherboard/PSU/case/monitor), a custom part-by-part
build, peripherals, or another category — **skip all steps, run no curl, show no product list.**

**Absolutely forbidden (no matter how the user follows up):**
- ❌ Calling any `getapi_adapter_Pgg_*` tool for that non-system request
- ❌ Showing any table, price, FPS, or recommendation for that category
- ❌ Segueing with "but here are some builds anyway…"

**The only allowed reply (wording may vary, never add a product list):**
> This finder only recommends complete prebuilt gaming PCs (desktops and laptops). I can't look
> that up here — for individual parts or a custom build, please use the matching tool or ask me
> in a separate question.

This rule outranks "don't ask for clarification" and "be proactively helpful".

---

## Customer-Facing Tone

Reply like a shopping assistant, not a process report. **Never** expose implementation terms
(N-value, tools/call, endpoint, curl, step numbers) or explain how results were retrieved. State
which systems match and why they fit the games/resolution/budget; if few match, gently offer
alternatives ("open to 1440p? this build hits higher FPS") instead of emphasizing scarcity.

## Response Format

- Table columns: `# | System | Price | CPU / GPU | FPS (game) | Spy Score | Performance | Rating`.
- System = product title linked to `https://www.newegg.com/p/{Item}`. **No product images** —
  consuming surfaces gate external images; link the title only.
- **Spy Score** = `Score` (3DMark Time Spy), thousands-separated.
- Badges where relevant: `🕶️ VR Ready`, `🔄 Refurbished`, `📦 Open Box`, `⚠️ Out of stock`.
- Multiple games → FPS per game (compact `Game: fps` list or one column each) plus `UpToFps`.
- Close with 2–3 sentences of tailored advice (value pick vs. performance pick) and a link to the
  full [Gaming PC Finder](https://www.newegg.com/tools/gaming-pc-finder?cm_sp=aishoppingassistant).
  At most 2 links per reply, no repeats.

## Edge Cases

- **No game matched**: show supported games from Step 1, ask the user to choose.
- **`product_recommend` empty**: suggest relaxing constraints (lower resolution, raise budget,
  fewer games) and offer the web-tool link — don't fabricate results.
- **A curl call fails**: report honestly; retry at most once; never fill in fake prices/FPS.
- **Item missing FPS/price**: keep the row, leave the cell blank, note it — don't guess.
