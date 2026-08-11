# Gaming PC Finder — raw HTTP contract

`scripts/pgg_api.py` is the normal way to fetch data. Read this file only when the script cannot be
used — no Python in the host, or only an HTTP/fetch tool available — or when you need a field the
script's slim view drops.

The finder endpoint accepts stateless JSON-RPC over plain HTTPS: no auth, no API key, no client
library, no `initialize` handshake, no session header. One POST per call.

**Endpoint**: `https://apis.newegg.com/ex-mcp/endpoint/gaming-pc-finder`

## Request shape

```
POST https://apis.newegg.com/ex-mcp/endpoint/gaming-pc-finder
Content-Type: application/json
Accept: application/json, text/event-stream

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "<operation>",
    "arguments": { "CountryCode": "USA", "CompanyCode": 1003, ... }
  }
}
```

`<operation>` is one of:

| Operation | `params.name` |
|---|---|
| `game_list` | `getapi_adapter_Pgg_game_list` |
| `property_list` | `getapi_adapter_Pgg_property_list` |
| `product_recommend` | `getapi_adapter_Pgg_product_recommend` |
| `product_search` | `getapi_adapter_Pgg_product_search` |

Arguments are exactly those documented in `SKILL.md` Steps 1–3 — same names, same types, same
required fields. `CountryCode` and `CompanyCode` are always required.

## Response shape

```json
{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"{\"GameInfos\":[...]}"}]}}
```

The payload the skill cares about is **`result.content[0].text`, a JSON string that must be parsed
again**. Some responses also carry the same object in `result.structuredContent` — prefer that when
present.

Failure signals, in order:
- HTTP status ≠ 200 → transport failure.
- `error` at the top level → JSON-RPC error (bad operation name, malformed arguments).
- `result.isError === true` → upstream rejected the arguments.

If the server answers as SSE (`data: {...}` lines), parse the last `data:` line as the envelope.

## The bundled client (preferred whenever Python is available)

`scripts/pgg_api.py` (Python 3, standard library only) wraps all of the above **and slims the
response** — `product_search` returns ~230 KB raw, which blows up context; the slim view of the
same call is ~3 KB.

```bash
python scripts/pgg_api.py game_list
python scripts/pgg_api.py property_list GameNValues=5171
python scripts/pgg_api.py product_recommend GameNValues=5171 ResolutionNValues=5015 ComputerType=D
python scripts/pgg_api.py product_search GameNValues=5171 ResolutionNValues=5015 ComputerType=D Budget=0-2500 Sort=4 PageIndex=1 PageSize=20 --limit 10
```

- Arguments are `Key=Value` pairs using the exact API argument names.
- `CountryCode=USA` / `CompanyCode=1003` are applied by default; override with `--country` /
  `--company`.
- `--limit N` caps printed items (default 20). `--raw` prints the full upstream JSON — only use it
  when a field outside the slim view is genuinely needed.
- Exit codes: `0` ok, `1` usage error, `2` transport/API error. Errors go to stderr and must be
  reported to the user honestly, never worked around with invented data.

Slim output fields per item: `Item`, `Url`, `Title`, `FinalPrice`, `Cpu`, `Gpu`, `Fps`
(`{game: fps}` for `product_recommend`, a scalar for `product_search`), `UpToFps`, `Score`,
`Level`, `PerformancePercentile`, `VrReady`, `Rating`, `Reviews`, `Instock`, `IsRefurbished`,
`IsOpenBoxed`, `ProductType`. `game_list` → `Games[] {N,Name}` + `Resolutions[] {N,Group}`;
`property_list` → `CpuTypes[]`, `GpuTypes[]` (vendor buckets, e.g. `Intel`/`AMD`), `HotBrands[]
{N,Name}`.

## Raw curl

```bash
curl -s -X POST https://apis.newegg.com/ex-mcp/endpoint/gaming-pc-finder \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"getapi_adapter_Pgg_game_list","arguments":{"CountryCode":"USA","CompanyCode":1003}}}'
```

Budget-filtered search, piped through `jq` to keep the output small:

```bash
curl -s -X POST https://apis.newegg.com/ex-mcp/endpoint/gaming-pc-finder \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"getapi_adapter_Pgg_product_search","arguments":{"PageIndex":1,"PageSize":20,"GameNValues":"5171","ResolutionNValues":"5015","ComputerType":"D","Budget":"0-2500","Sort":4,"CountryCode":"USA","CompanyCode":1003}}}' \
  | jq -r '.result.content[0].text' \
  | jq '[.Items[:10][] | {Item, Title: .Description.Title, Price: .FinalPrice, Cpu, Gpu, Fps, Score, Rating: .Review.RatingOneDecimal, Reviews: .Review.HumanRating, Instock}]'
```

**Never dump a raw `product_search` response into the reply or into context unfiltered.**

## Hosts with only a fetch/HTTP tool (no shell)

Issue the same POST with the fetch tool, then parse `result.content[0].text`. JavaScript form:

```js
const res = await fetch("https://apis.newegg.com/ex-mcp/endpoint/gaming-pc-finder", {
  method: "POST",
  headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream" },
  body: JSON.stringify({
    jsonrpc: "2.0", id: 1, method: "tools/call",
    params: { name: "getapi_adapter_Pgg_game_list", arguments: { CountryCode: "USA", CompanyCode: 1003 } },
  }),
});
const data = JSON.parse((await res.json()).result.content[0].text);
```

For `product_search` on such a host, always send `PageSize` ≤ 20 and read only the fields listed in
the slim-view list above.
