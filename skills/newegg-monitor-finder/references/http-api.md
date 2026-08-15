# Newegg product search — raw HTTP contract

`scripts/monitor_api.py` is the normal way to fetch data. Read this file only when the script
cannot be used — no Python in the host, or only an HTTP/fetch tool available — or when you need a
field the script's slim view drops.

The product-search endpoint accepts stateless JSON-RPC over plain HTTPS: no auth, no API key, no
client library, no MCP server registration, no `initialize` handshake, no session header. One POST
per call.

**Endpoint**: `https://apis.newegg.com/ex-mcp/endpoint/product-search`
**Tool name**: `newegg product search` (with spaces — exact string)

**Required header on every request**: every call must carry `x-skill: newegg-monitor-finder` alongside
`Content-Type`. It identifies the calling skill to the endpoint. The bundled client sends it
automatically; add it yourself when calling raw.

## Request shape

```
POST https://apis.newegg.com/ex-mcp/endpoint/product-search
Content-Type: application/json
Accept: application/json, text/event-stream
x-skill: newegg-monitor-finder

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "newegg product search",
    "arguments": {
      "query": "144Hz gaming monitor",
      "minPrice": null,
      "maxPrice": 350,
      "order": 15,
      "page": 1
    }
  }
}
```

| Argument | Type | Required | Notes |
|---|---|---|---|
| `query` | string | Yes | Search keyword — **English only** (see below) |
| `minPrice` / `maxPrice` | number | No | Inclusive; omit or `null` for no filter |
| `order` | integer | No | `15` Best Selling, `1` Best Rating, `2` Lowest Price, `3` Highest Price, `4` Most Reviews, `8` Featured (API default) |
| `page` | integer | No | **1-based**; page size is fixed at 30 |

### Argument traps — these return an empty result set, not an error

The API accepts out-of-range arguments and answers `{"total": 0, "products": []}`, which is
indistinguishable from a genuine "nothing in stock". When calling raw (no script), validate
these yourself before trusting an empty response:

| Trap | Behaviour | Do instead |
|---|---|---|
| Non-English `query` (e.g. `电竞显示器`) | `total: 0` | Translate to an English term first — the catalog has no CJK index |
| `page: 0` | `total: 0` | Page numbering is 1-based; start at `1` |
| `minPrice` > `maxPrice` | `total: 0` | Check the ordering before sending |
| Negative price | `total: 0` | Clamp to `0` / omit the field |

`scripts/monitor_api.py` rejects all four with exit code `1` up front.

## Response shape

```json
{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"{\"products\":[...]}"}]}}
```

The payload the skill cares about is **`result.content[0].text`, a JSON string that must be parsed
again**. Some responses also carry the same object in `result.structuredContent` — prefer that when
present. Top-level fields: `total`, `page`, `pageSize`, `totalPage`, `products[]`.

Failure signals, in order:
- HTTP status ≠ 200 → transport failure.
- `error` at the top level → JSON-RPC error (bad tool name, malformed arguments).
- `result.isError === true` → upstream rejected the arguments.

If the server answers as SSE (`data: {...}` lines), parse the last `data:` line as the envelope.

## The bundled client (preferred whenever Python is available)

`scripts/monitor_api.py` (Python 3, standard library only) wraps all of the above, **parses the
spec HTML**, and **slims the response** — a full page raw is ~110 KB, slimmed it is ~21 KB.

```bash
python scripts/monitor_api.py "144Hz gaming monitor"
python scripts/monitor_api.py "OLED gaming monitor" --max-price 900 --order 15
python scripts/monitor_api.py "curved ultrawide gaming monitor" --min-price 350 --max-price 800 --limit 30
python scripts/monitor_api.py "240Hz gaming monitor" --page 2
```

- Options: `--min-price`, `--max-price`, `--order`, `--page`, `--limit N` (default 30), `--raw`,
  `--timeout N`.
- Exit codes: `0` ok, `1` usage error, `2` transport/API error. Errors go to stderr and must be
  reported to the user honestly, never worked around with invented data.
- Exit `1` also covers the four traps above (non-English query, `--page 0`, inverted price range,
  negative price) — fix the argument and re-run; do not report it to the user as "no results".

Slim output per product: `ItemNumber`, `Url`, `Title`, `FinalPrice`, `PriceSaveText`, `Rating`,
`Reviews`, `IsRefurbished`, `SizeInches` (numeric, for local size filtering), `IsCurved`,
`AdaptiveSync[]` (normalized, e.g. `FreeSync Premium Pro`, `G-Sync Compatible`), plus the parsed
spec fields `Screen Size`, `Resolution`, `Refresh Rate`, `Response Time`, `Panel`, `Aspect Ratio`,
`Curved Surface Screen`, `Display Colors`. **Fields that are absent upstream are omitted** — treat a
missing key as unknown and render `—`.

## Raw curl

```bash
curl -s -X POST https://apis.newegg.com/ex-mcp/endpoint/product-search \
  -H 'Content-Type: application/json' \
  -H 'x-skill: newegg-monitor-finder' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"newegg product search","arguments":{"query":"144Hz gaming monitor","maxPrice":350,"order":15,"page":1}}}' \
  | jq -r '.result.content[0].text' \
  | jq '[.products[:10][] | {ItemNumber, Title: .WebDescription, Price: .Price.FinalPrice, Rating: .Price.RatingOneDecimal, Specs: .ViewDescription}]'
```

On Windows use `curl.exe` explicitly — plain `curl` in PowerShell is the `Invoke-WebRequest` alias
and does not understand `-d`. Prefer the bundled Python client there; it sidesteps the quoting
problem entirely.

**Never dump a raw response into the reply or into context unfiltered.**

## Hosts with only a fetch/HTTP tool (no shell)

Issue the same POST with the fetch tool, then parse `result.content[0].text`. JavaScript form:

```js
const res = await fetch("https://apis.newegg.com/ex-mcp/endpoint/product-search", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json, text/event-stream",
    "x-skill": "newegg-monitor-finder",
  },
  body: JSON.stringify({
    jsonrpc: "2.0", id: 1, method: "tools/call",
    params: {
      name: "newegg product search",
      arguments: { query: "144Hz gaming monitor", maxPrice: 350, order: 15, page: 1 },
    },
  }),
});
const data = JSON.parse((await res.json()).result.content[0].text);
const specs = (vd) => Object.fromEntries(
  [...(vd || "").matchAll(/<b>(.*?):<\/b>\s*([^<]*)/g)].map((m) => [m[1].trim(), m[2].trim()])
);
```

Read only the fields listed in the slim-view list above; ignore `ImageList` / `BulletDescription`
bulk when summarizing.
