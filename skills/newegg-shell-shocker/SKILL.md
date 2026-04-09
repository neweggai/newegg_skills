---
name: newegg-shell-shocker
description: 
  Query Newegg Shell Shocker flash deal products. Use this skill when users mention Shell Shocker, Shell Shocker deals,
  Newegg flash deals, today's flash deals, Newegg promotions, flash deal list, limited-time specials.
keywords: shell shocker, newegg, flash deal, 闪促, 限时特价.
allowed-tools: bash, read_file
---

# Newegg Shell Shocker

Query Newegg Shell Shocker daily and next-day flash deal products.

## Agent execution rules (read first)

- **Do not** call `ask_clarification` for this task. The data source (single public GET JSON) and the output format (Markdown tables below) are **fully specified** — this is **not** `missing_info`, `ambiguous_requirement`, or `approach_choice`.
- **Immediately** after loading this skill, use the **`bash` tool** to run curl. **Do not** ask the user how to fetch data or which output format they prefer.
- Run exactly:

```bash
curl -sS "https://www.newegg.com/api/Common/TomorrowShellShocker"
```

- Treat stdout as JSON and build the tables in **Response Format**. If curl fails (non-zero exit) or the body is not valid JSON, report the error in your reply — still **without** asking the user to choose a fetch method.

## Trigger Scenarios

- User asks "What's on Shell Shocker"
- User asks "Today's flash deals" / "Newegg flash deals"
- User searches for Shell Shocker prices of specific products
- User requests to view Newegg limited-time special list

## API

- **Method**: GET
- **URL**: `https://www.newegg.com/api/Common/TomorrowShellShocker`
- **Request**: No request body

## Response Structure

Root object contains:
- `TodayItems` (array) - Today's flash deal items
- `TomorrowItems` (array) - Tomorrow's flash deal items

Each item element contains an `ItemBase` object, from which to extract:

| Field | Path | Description |
|------|------|------|
| Item Number | `ItemBase.Item` | e.g., `32-508-055` |
| Item Title | `ItemBase.Description.Title` | Full item name |
| Original Price | `ItemBase.OriginalUnitPrice` | Original price (USD) |
| Flash Deal Price | `ItemBase.FinalPrice` | Final price (USD) |
| Image Filename | `ItemBase.Image.Normal.ImageName` | e.g., `32-508-055-V01.jpg` |
| Promotion Info | `ItemBase.PromotionInfo.PromotionText` | e.g., free gifts, additional discounts, etc. |

**Image URL Construction**:
```
https://c1.neweggimages.com/ProductImageCompressAll/{ImageName}
```
例如：`https://c1.neweggimages.com/ProductImageCompressAll/32-508-055-V01.jpg`

**Product Link Construction**:
```
https://www.newegg.com/p/{Item}
```
例如：`https://www.newegg.com/p/32-508-055`

## Execution Flow

1. Call the API with **`bash`** using the curl command in **Agent execution rules** (no other tool for the HTTP request).
2. Parse JSON, iterate through `TodayItems` and `TomorrowItems`
3. Skip rows where `ItemBase` is `null` (usually Combo rows)
4. Extract fields and format the response per **Response Format**

## Response Format

Return a clear product table containing:

```
## Today's Flash Deals (TodayItems)

| Item Number | Product Name | Original Price | Flash Deal Price | Image |
|---------|---------|------|-------|------|
| 32-508-055 | [adidas $50 Gift Card](https://www.newegg.com/p/32-508-055) | $50 | $50 | [Image](https://c1.neweggimages.com/ProductImageCompressAll/32-508-055-V01.jpg) |
| ... | ... | ... | ... | ... |

## Tomorrow's Flash Deals (TomorrowItems)

| Item Number | Product Name | Original Price | Flash Deal Price | Image |
|---------|---------|------|-------|------|
| ... | ... | ... | ... | ... |
```

**If promotion information exists**, display below the product name:
```
🎁 Promotion: Free $15 Adidas eGift Card w/ purchase
```

## Edge Cases

- **Empty Data**: If `TodayItems` or `TomorrowItems` is empty or doesn't exist, clearly inform the user
- **Combo Rows**: Skip rows that only have `ComboBase` unless the user specifically requests combo details
- **HTTP Errors**: Report status code and error message
- **Invalid JSON**: Briefly report parsing failure

## Example Request

```bash
curl -sS "https://www.newegg.com/api/Common/TomorrowShellShocker"
```

(`-sS` keeps output clean but still surfaces curl errors.)

## Notes

- This API requires no authentication
- Returned data is in English; product names can be translated if needed
- Prices are in USD
- Image URLs support multiple sizes; default to `ProductImageCompressAll` path
