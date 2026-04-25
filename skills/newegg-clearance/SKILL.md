---
name: newegg-clearance
license: MIT
description: >-
  Browse Newegg Clearance store products — discounted open-box, overstocked,
  and promotional items across all categories on Newegg (https://www.newegg.com).
  Use this skill when users want to find clearance deals, discounted items,
  open-box products, or browse the Newegg promotion store.
  Triggers: "newegg clearance", "clearance deals", "newegg open box deals",
  "newegg discounted items", "newegg promotion store", "newegg特价清仓", "清仓商品".
---

# Newegg Clearance Store

Browse the Newegg Clearance / Promotion Store via MCP over HTTP using standard JSON-RPC.
Use the `bash` tool to call the endpoint — no MCP client registration required.

## Agent Execution Rules

- **Do not** ask for clarification. The data source and output format are fully specified — call immediately.
- Use the **`bash`** tool to run the curl command below.
- On curl failure or invalid JSON, report the error directly.
- Display the **top 10 products** from the response.
- **Browse all** link to "https://www.newegg.com/Clearance-Store/EventSaleStore/ID-697"
- **Don't show image

## API Call

```bash
curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/website-www-tool" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "getapi_adapter_Jss_promotionStore",
      "arguments": {
        "storeId": 697,
        "CountryCode": "USA",
        "CompanyCode": 1003
      }
    }
  }'
```

> If the call returns a tool-not-found error, first run `tools/list` to discover the correct tool name:
> ```bash
> curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/website-www-tool" \
>   -H "Content-Type: application/json" \
>   -d '{"jsonrpc":"2.0","id":0,"method":"tools/list"}'
> ```

## Response Parsing

The MCP response wraps a store catalog object. Parse the path:

```
response → result.content[0].text → (parse as JSON) → root object
```

### Root Fields

| Field            | Description                              |
|------------------|------------------------------------------|
| `Products`       | Array of product entries (up to 36/page) |
| `TotalItemCount` | Total products in the clearance store    |

### Product Entry Fields

Each entry in `Products` has a top-level `ProductNumber` and an `ItemCell` object.

| Field                                            | Description                                        |
|--------------------------------------------------|----------------------------------------------------|
| `ProductNumber`                                  | Item number, e.g. `"17-701-025"`                   |
| `ItemCell.Description.Title`                     | Full product title                                 |
| `ItemCell.Description.SimplifiedLineDescription` | Shortened product title (prefer this if non-empty) |
| `ItemCell.ItemManufactory.Manufactory`           | Brand name                                         |
| `ItemCell.ItemPriceRange.PriceRangeMin`          | Lowest available price in USD                      |
| `ItemCell.ItemPriceRange.PriceRangeMax`          | Highest available price in USD                     |
| `ItemCell.Review.RatingOneDecimal`               | Avg rating (0–5, one decimal), e.g. `4.3`          |
| `ItemCell.Review.HumanRating`                    | Number of reviews                                  |
| `ItemCell.Feature.IsOpenBoxed`                   | `true` if open-box item                            |
| `ItemCell.Feature.IsRefurbished`                 | `true` if refurbished item                         |
| `ItemCell.Subcategory.SubcategoryDescription`    | Category label, e.g. `"Power Supplies"`            |

**URL construction:**
- Product page: `https://www.newegg.com/p/{ProductNumber}`

**Price display logic:**
- If `ItemPriceRange` is not null: show `PriceRangeMin` as the price (and `PriceRangeMax` if different)
- If `ItemPriceRange` is null and `FinalPrice` > 0: show `FinalPrice`
- If both are unavailable: show `"—"`

## Response Format

```
## 🏷️ Newegg Clearance Store — Top 10 Deals

| # | Product | Brand | Price | Rating | Reviews |
|---|---------|-------|-------|--------|---------|
| 1 | [SimplifiedLineDescription](https://www.newegg.com/p/{ProductNumber}) | Manufactory | $PriceRangeMin | ⭐ RatingOneDecimal | HumanRating |
| 2 | ... | ... | ... | ... | ... |
...

📦 {TotalItemCount} total clearance items available
```

- If `IsOpenBoxed` is true, append `📦 Open Box` badge after the product name
- If `IsRefurbished` is true, append `🔄 Refurbished` badge after the product name
- If `RatingOneDecimal` is 0 and `HumanRating` is 0, show `—` for both rating columns
- Prefer `SimplifiedLineDescription` for the display name; fall back to `Title` if empty
- Truncate product names longer than 80 characters with `…`

## Edge Cases

- **HTTP error or curl failure**: Report status code and body; do not retry.
- **`result.error` in response**: Display `error.message` to the user.
- **Empty `Products` array**: Inform the user the clearance store appears empty.
- **`ItemPriceRange` is null and `FinalPrice` is 0**: Display price as `"—"`.
