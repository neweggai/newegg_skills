---
name: newegg-laptop-finder
description: >-
  Find the perfect laptop on Newegg by asking the user about their needs and
  returning the top 10 matching laptops with direct purchase links.
  Use this skill whenever users want help choosing or finding a laptop — even if they
  don't mention Newegg by name. Always trigger on phrases like: "help me find a laptop",
  "what laptop should I buy", "recommend a laptop for gaming/work/school/video editing",
  "I need a laptop under $X", "best laptop for students", "find me a good laptop",
  "laptop recommendation", "我想买个笔记本", "推荐笔记本电脑", "给我找一款游戏本",
  "帮我找笔记本", or any question about choosing or comparing laptops for purchase.
  This skill handles the full flow: gathering requirements → searching Newegg → showing
  top 10 results with clickable buy links.
---

# Newegg Laptop Finder

Help users find their perfect laptop by understanding their needs, then searching the
Newegg catalog to present the top 10 best-matching options — each with a direct link
to purchase on Newegg.com.

## Overview

1. **Gather requirements** — Ask a short, friendly set of questions
2. **Build a targeted query** — Map their needs to proven search terms
3. **Fetch results from Newegg** — Call the product search API
4. **Display top 10** — Show a clean results table with clickable purchase links

---

## Step 1: Gather User Requirements

Ask the user a few focused questions in a warm, conversational tone in one message.
Aim for 2–3 questions total. If the user has already given you details (e.g., "gaming
laptop under $1000"), extract what you can and only ask about what's genuinely missing.

### Always ask:

**1. Primary use** — What will they mainly use the laptop for?

| Use Case | Examples |
|----------|---------|
| 🎮 Gaming | gaming, AAA games, FPS, esports |
| 💼 Work / Business / Productivity | office, remote work, presentations |
| 🎓 School / Study / Everyday | note-taking, browsing, streaming |
| 🎨 Creative (photo/video/design) | video editing, photo editing, 3D work |

**2. Budget** — What's their price range?

Accept any phrasing: "under $600", "$800 to $1200", "around $1000", "my budget is $1500".
If they're unsure, suggest: Under $800 / $800–$1,200 / $1,200–$1,800 / $1,800+

### Optional follow-ups (ask 1 max if not already clear):

- Any strong brand preference? (ASUS, MSI, Lenovo, Dell, HP, Acer, Razer, etc.)
- Prefer portability (thin & light) or max performance?
- Screen size preference? 14–15" (portable) / 16–17" (larger screen)

Keep it short. If the user just wants to browse, start with the best general query.

---

## Step 2: Build the Search Query

Use these **proven queries** that return real results from the Newegg API:

| Use Case | Primary Query | Fallback Query |
|----------|--------------|---------------|
| Gaming (any price) | `gaming laptop` | `RTX laptop` |
| Creative / video editing | `thin laptop` | `notebook computer` |
| Work / Business | `notebook computer` | `thin laptop` |
| School / Study / Everyday | `budget laptop` | `notebook computer` |
| Thin & light / portable | `thin laptop` | `notebook computer` |
| General / unsure | `notebook computer` | `thin laptop` |

**Enhance the query with brand if specified:**
Add brand name to the query (e.g., `"ASUS gaming laptop"`, `"Lenovo notebook computer"`).
Note: brand-specific queries may return fewer results; if < 5 results, drop the brand.

**Do NOT use** these queries — they return 0 or irrelevant results on Newegg:
`chromebook`, `business laptop`, `student laptop`, `student notebook`, `MacBook`
(For MacBook/macOS requests, tell the user Newegg primarily carries Windows laptops
and show the best thin & light alternatives.)

---

## Step 3: Call the Newegg Product Search API

Use the `bash` tool. The **tool name is `"newegg product search"`** (with spaces — this is critical).

### Primary call (with price filter if budget given):

```bash
curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/product-search" \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

### Budget → price filter mapping:

| Budget stated | minPrice | maxPrice |
|---------------|----------|----------|
| Under $500 | null | 600 |
| Under $800 | null | 900 |
| $500–$800 | 400 | 900 |
| $800–$1,200 | 700 | 1400 |
| $1,200–$1,800 | 1000 | 2000 |
| $1,800+ | 1500 | null |
| Around $X | X × 0.8 | X × 1.2 |

Use **slightly wider ranges than stated** — the catalog is limited and narrow filters
often return fewer than 10 results. If the price-filtered query returns fewer than 5
products, **retry without price filters** and note in your response which products fall
closest to the user's budget.

Sort order: `15` (Best Selling) by default. Use `1` for "best rated", `2` for "cheapest".

### Parse the response:

```
response → result.content[0].text → parse as JSON → products array
```

Take the **first 10 items** from `products`.

### Key product fields:

| Field | Notes |
|-------|-------|
| `ItemNumber` | Build URL: `https://www.newegg.com/p/{ItemNumber}` |
| `WebDescription` | Product title (use as link text) |
| `Price.FinalPrice` | **Numeric price** — format as `$X.XX`. (CurrentPriceText is often empty) |
| `Price.OriginalPriceText` | Original price before discount (may be empty) |
| `Price.PriceSaveText` | Savings text e.g. "$50.00 (10%)" (may be empty) |
| `Price.RatingOneDecimal` | Star rating 0–5 |
| `Price.HumanRating` | Number of reviews |
| `IsRefurbished` | Show 🔄 tag if true |

---

## Step 4: Display the Top 10 Results

Present results as a clean markdown table. Every product name **must be a clickable
link** so the user can go directly to Newegg to view specs and purchase.

```
## 🖥️ Top 10 Laptops for [Use Case] — [Budget]

| # | Laptop | Price | Rating | Reviews |
|---|--------|-------|--------|---------|
| 1 | [Product Name](https://www.newegg.com/p/ITEM_NUMBER) | $XXX | ⭐ X.X | NNN |
| 2 | [Product Name](https://www.newegg.com/p/ITEM_NUMBER) | $XXX | ⭐ X.X | NNN |
...
| 10 | ... | ... | ... | ... |

💡 **Click any laptop name to view full specs and buy on Newegg.**

🔗 [See more laptops on Newegg →](https://www.newegg.com/Laptops-Notebooks/SubCategory/ID-32?d=QUERY)
```

**Formatting rules:**
- Format `FinalPrice` as `$X` (no decimals if `.00`) or `$X.XX`
- If `PriceSaveText` is non-empty: add `> 💸 Save PriceSaveText` below the row
- If `IsRefurbished` is true: append ` 🔄` to product name in the link
- If rating is 0 and reviews is 0: show `—` instead

**After the table**, write **2–3 sentences of buying advice** tailored to the use case:
- 🎮 Gaming: what GPU tier is in the results and what frame rates to expect
- 🎓 School/Everyday: battery life, weight, and value tips
- 🎨 Creative: RAM, display quality, and GPU rendering capability
- 💼 Work: keyboard, display, portability, and build quality notes

---

## Edge Cases

- **Fewer than 5 price-filtered results**: Retry without price filters. Note in your
  response which results are within or near the user's stated budget.
- **Fewer than 10 results total**: Show what's available. Offer to try a different
  query or remove filters.
- **Results look wrong** (only accessories, no laptops): Retry the fallback query from
  the table above.
- **Want to c