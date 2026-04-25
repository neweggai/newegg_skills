---
name: newegg-compare
description: >-
  Compare specs of 2–5 products side-by-side on Newegg. Use this skill whenever
  the user wants to compare products, see specs side by side, check differences
  between models, or evaluate options before buying — even if they don't say
  "compare" explicitly. Triggers: "compare these GPUs on newegg", "which is
  better RTX 4070 vs 4080", "比较这几个商品的规格", "side by side specs",
  "newegg compare", "help me pick between", "what are the differences between",
  "对比 Newegg 商品".
---

# Newegg Product Comparison

Compare up to 5 products side-by-side using Newegg's comparison page. This skill
handles the full flow: searching for products, resolving item numbers, building
the comparison URL, and presenting a clean spec summary.

---

## Step 1 — Identify the products to compare

Parse the user's message to extract 2–5 product names or descriptions. If the
user only mentions one product, ask them which other products they'd like to
compare it against before proceeding.

---

## Step 2 — Search for each product via the API

For each product, call the Newegg search API using `bash`:

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
        "query": "<SEARCH TERM>"
      }
    }
  }'
```

**Parse the response:**
```
response → result.content[0].text → (parse as JSON) → products array
```

Each product has:
- `ItemNumber` — e.g. `"14-126-761"` — this is what you need for the comparison URL
- `WebDescription` — product title
- `Price.CurrentPriceText` — current price
- `Price.RatingOneDecimal` — avg rating

**If multiple results:** Show the top 3 results as a numbered list for that product
and ask the user to confirm which one they want to compare. Wait for confirmation
before proceeding.

**If no results:** Tell the user and ask them to rephrase the search term.

> Note: If the API returns `"Unknown tool"`, run `tools/list` first to discover
> the correct tool name:
> ```bash
> curl -sS -X POST "https://apis.newegg.com/ex-mcp/endpoint/product-search" \
>   -H "Content-Type: application/json" \
>   -d '{"jsonrpc":"2.0","id":0,"method":"tools/list"}'
> ```

---

## Step 3 — Build the comparison URL

Once you have the `ItemNumber` for each product, join them with `%2C` and append
to the base URL:

```
https://www.newegg.com/Product/Productcompare?compareall=true&CompareItemList=<ItemNumber1>%2C<ItemNumber2>%2C...
```

**Example** (3 products):
```
https://www.newegg.com/Product/Productcompare?compareall=true&CompareItemList=14-126-761%2C14-137-914%2C14-137-933
```

Maximum 5 item numbers. Strip any whitespace from item numbers before joining.

---

## Step 4 — Load the comparison page in the browser

The comparison page is JavaScript-rendered, so use the browser navigation tool
to load it and extract the rendered content:

```
Navigate to: <comparison URL from Step 3>
```

After navigating, wait for the page to load (the comparison table should appear),
then extract the full page text content.

---

## Step 5 — Parse and display the comparison

From the extracted page text, identify the spec rows and product columns. Present
the comparison as a clean Markdown table:

```
## Newegg Comparison: [Product A] vs [Product B] vs ...

🔗 [View on Newegg](<comparison URL>)

| Spec | [Product A short name] | [Product B short name] | ... |
|------|------------------------|------------------------|-----|
| Price | $XXX | $XXX | ... |
| [spec] | [value] | [value] | ... |
...

💡 **Summary:** [2-3 sentence recommendation based on the specs, highlighting
key differences that matter for the user's apparent use case]
```

**Presentation tips:**
- Use short product names in column headers (remove brand prefix if it makes the
  table cleaner, but keep the model number)
- Group specs logically: pricing first, then performance specs, then physical
  specs, then connectivity
- If a spec value is identical across all products, you can still include it but
  it's lower priority
- Highlight the "winner" in each row with **bold** if there is a clear winner
- If the page fails to load or returns no comparison data, provide the URL to
  the user directly so they can open it in their browser, and offer to summarize
  specs from your training knowledge

---

## Edge Cases

| Situation | Action |
|-----------|--------|
| User gives only 1 product | Ask which products to compare it with |
| Search returns no results | Ask user to rephrase or check the product name |
| More than 5 products requested | Inform user the limit is 5 and ask which 5 to compare |
| Item number not found in search | Note it and proceed with the products found |
| Comparison page fails to load | Provide the URL directly; offer to summarize from training knowledge |
| Products are from very different categories | Still proceed; the comparison table will show the differences clearly |
