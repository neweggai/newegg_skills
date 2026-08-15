---
name: newegg-product-search
license: MIT
description: >-
  Search for products on Newegg (https://www.newegg.com), a leading online electronics retailer
  specializing in CPUs, GPUs, motherboards, RAM, SSDs, laptops, monitors, PC peripherals,
  networking equipment, and consumer electronics.
  Use this skill when users want to search, find, browse, or look up products on Newegg by
  keyword, model name, or category. Supports price range filtering, pagination, and sort options.
  Triggers: "find on newegg", "search newegg", "newegg price", "newegg GPU/CPU/SSD/laptop",
  "newegg products", "shop newegg", 搜索Newegg商品, 查找产品, Newegg搜索.
---

# Newegg Product Search

Search Newegg products via MCP over HTTP using standard JSON-RPC. Use the `bash` tool to call
the endpoint — no MCP client registration required.

## Agent Execution Rules

- **Do not** ask for clarification. Infer `query` and optional parameters from the user's message and call immediately.
- Use the **`bash`** tool to run the curl command below.
- On curl failure or invalid JSON, report the error directly.

## API Call

**Required header on every request**: all calls to `apis.newegg.com/ex-mcp/...` must carry `x-skill: newegg-product-search` in addition to `Content-Type`. It identifies the calling skill to the endpoint — include it even when you assemble a request by hand rather than copying an example below.

```bash
curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/product-search" \
  -H "Content-Type: application/json" \
  -H "x-skill: newegg-product-search" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "searchPost",
      "arguments": {
        "query": "<QUERY>"
      }
    }
  }'
```

Replace `<QUERY>` with the user's search term. Add optional fields inside `"arguments"` as needed.

> If the call returns a tool-not-found error, first run `tools/list` to discover the correct tool name:
> ```bash
> curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/product-search" \
>   -H "Content-Type: application/json" \
>   -H "x-skill: newegg-product-search" \
>   -d '{"jsonrpc":"2.0","id":0,"method":"tools/list"}'
> ```

## Parameters

| Parameter  | Type    | Required | Default | Description |
|------------|---------|----------|---------|-------------|
| `query`    | string  | **Yes**  | —       | Search keyword or product name |
| `order`    | integer | No       | `8`     | Sort order — see values below |
| `page`     | integer | No       | `1`     | Page number (min: 1) |
| `minPrice` | number  | No       | null    | Minimum price in USD (inclusive) |
| `maxPrice` | number  | No       | null    | Maximum price in USD (inclusive) |

### `order` Values

| Value | Sort By            |
|-------|--------------------|
| `1`   | Best Rating        |
| `2`   | Lowest Price       |
| `3`   | Highest Price      |
| `4`   | Most Reviews       |
| `6`   | Name A → Z         |
| `7`   | Name Z → A         |
| `8`   | Featured *(default)* |
| `14`  | Release Date       |
| `15`  | Best Selling       |
| `16`  | Seller Rating      |
| `22`  | Sales Volume       |

**Mapping user intent → order:**
"cheapest" → `2` · "most expensive" → `3` · "best rated" → `1` · "most reviewed" → `4` · "newest" → `14` · "best selling" → `15`

## Response Parsing

The MCP response wraps a `PageProducts` object. Parse the path:

```
response → result.content[0].text → (parse as JSON) → PageProducts
```

### PageProducts fields

| Field       | Description                    |
|-------------|-------------------------------|
| `page`      | Current page number            |
| `pageSize`  | Items per page (typically 20)  |
| `total`     | Total matching products        |
| `totalPage` | Total pages                    |
| `products`  | Array of `ProductItem`         |

### ProductItem fields

| Field                       | Description                                      |
|-----------------------------|--------------------------------------------------|
| `ItemNumber`                | Item number, e.g. `"24-012-083"`                 |
| `WebDescription`            | Product title                                    |
| `Price.CurrentPriceText`    | Current price, e.g. `"$159.99"`                  |
| `Price.OriginalPriceText`   | Original price (show if differs from current)    |
| `Price.PriceSaveText`       | Savings text, e.g. `"$90.00 (36%)"` (if on sale)|
| `Price.RatingOneDecimal`    | Avg rating (0–5, one decimal), e.g. `4.4`        |
| `Price.HumanRating`         | Number of reviews, e.g. `850`                    |
| `ImageName`                 | Image filename for URL construction              |
| `IsRefurbished`             | `true` if refurbished item                       |

**URL construction:**
- Product page: `https://www.newegg.com/p/{ItemNumber}`
- Product image: `https://c1.neweggimages.com/productimage/nb300/{ImageName}`

## Response Format

```
## Newegg Search: "{query}"

| # | Product | Price | Rating | Reviews |
|---|---------|-------|--------|---------|
| 1 | [WebDescription](https://www.newegg.com/p/{ItemNumber}) | CurrentPriceText | ⭐ RatingOneDecimal | HumanRating |
| 2 | ... | ... | ... | ... |

📄 Page {page} / {totalPage}  ·  {total} total results
🔗 [View all on Newegg](https://www.newegg.com/p/pl?d={query})
```

- If item is on sale, append savings below its row: `> 💸 Save PriceSaveText (was OriginalPriceText)`
- If `IsRefurbished` is true, append `🔄 Refurbished` to the product name
- If price filter applied: `💰 Price: $minPrice – $maxPrice`
- If no results: inform the user and suggest broadening the search or removing filters
- Offer to load the next page if `page < totalPage`

## Edge Cases

- **HTTP error or curl failure**: Report status code and body; do not retry.
- **`result.error` in response**: Display `error.message` to the user.
- **Empty `products` array**: Tell the user no results were found; suggest adjusting `query` or removing price filters.
