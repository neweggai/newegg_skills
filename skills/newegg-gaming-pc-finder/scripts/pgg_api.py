#!/usr/bin/env python3
"""Newegg Gaming PC Finder — direct API client (no MCP client required).

The Gaming PC Finder endpoint speaks stateless JSON-RPC over plain HTTPS, so any
agent with a shell can call it without an MCP server configured.

Usage:
    python pgg_api.py game_list
    python pgg_api.py property_list GameNValues=5171
    python pgg_api.py product_recommend GameNValues=5171 ResolutionNValues=5015 ComputerType=D
    python pgg_api.py product_search GameNValues=5171 ResolutionNValues=5015 \
        Budget=0-2500 Sort=4 PageIndex=1 PageSize=20

Options:
    --raw          print the full upstream JSON instead of the slimmed view
    --limit N      max items to print (default 20; slim mode only)
    --country XX   CountryCode (default USA)
    --company N    CompanyCode (default 1003)
    --timeout N    seconds (default 30)

Exit codes: 0 ok, 1 usage error, 2 transport/API error.
"""

import json
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://apis.newegg.com/ex-mcp/endpoint/gaming-pc-finder"
# Identifies the calling skill to the endpoint; sent on every request.
SKILL_NAME = "newegg-gaming-pc-finder"

METHODS = {
    "game_list": "getapi_adapter_Pgg_game_list",
    "property_list": "getapi_adapter_Pgg_property_list",
    "product_recommend": "getapi_adapter_Pgg_product_recommend",
    "product_search": "getapi_adapter_Pgg_product_search",
}

INT_ARGS = {"CompanyCode", "PageIndex", "PageSize", "Sort"}


def call(tool, arguments, timeout=30):
    """POST one JSON-RPC tools/call and return the decoded payload dict."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": METHODS[tool], "arguments": arguments},
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "x-skill": SKILL_NAME,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:  # noqa: PERF203 - one call, one handler
        die(f"HTTP {exc.code} from finder API: {exc.read().decode('utf-8', 'replace')[:400]}")
    except urllib.error.URLError as exc:
        die(f"cannot reach finder API: {exc.reason}")

    # A streamable-http server may answer as SSE; take the last data: line.
    if body.lstrip().startswith("event:") or body.lstrip().startswith("data:"):
        data_lines = [ln[5:].strip() for ln in body.splitlines() if ln.startswith("data:")]
        if not data_lines:
            die("empty SSE response from finder API")
        body = data_lines[-1]

    envelope = json.loads(body)
    if "error" in envelope:
        die(f"finder API error: {json.dumps(envelope['error'])[:400]}")
    result = envelope.get("result") or {}
    if result.get("isError"):
        die(f"finder API returned isError: {json.dumps(result)[:400]}")
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content") or []
    if not content:
        die("finder API returned no content")
    return json.loads(content[0]["text"])


def fps_of(item):
    """Per-game FPS: recommend returns GameFpsInfos[], search returns a scalar Fps."""
    infos = item.get("GameFpsInfos")
    if infos:
        return {i.get("Name"): i.get("Fps") for i in infos}
    return item.get("Fps")


def slim_item(item):
    desc = item.get("Description") or {}
    review = item.get("Review") or {}
    feature = item.get("Feature") or {}
    number = item.get("Item")
    return {
        "Item": number,
        "Url": f"https://www.newegg.com/p/{number}" if number else None,
        "Title": desc.get("Title") or desc.get("WebDescription"),
        "FinalPrice": item.get("FinalPrice"),
        "Cpu": item.get("Cpu"),
        "Gpu": item.get("Gpu"),
        "Fps": fps_of(item),
        "UpToFps": item.get("UpToFps"),
        "Score": item.get("Score"),
        "Level": item.get("Level"),
        "PerformancePercentile": item.get("PerformancePercentile"),
        "VrReady": item.get("VrReady"),
        "Rating": review.get("RatingOneDecimal"),
        "Reviews": review.get("HumanRating"),
        "Instock": item.get("Instock"),
        "IsRefurbished": feature.get("IsRefurbished"),
        "IsOpenBoxed": feature.get("IsOpenBoxed"),
        "ProductType": feature.get("ProductType"),
    }


def names(bucket):
    return [b.get("Name") for b in (bucket or [])]


def slim(tool, data, limit):
    if tool == "game_list":
        return {
            "Games": [{"N": g["N"], "Name": g["Name"]} for g in data.get("GameInfos") or []],
            "Resolutions": [
                {"N": r["N"], "Group": r["Group"]} for r in data.get("ResolutionInfos") or []
            ],
        }
    if tool == "property_list":
        return {
            "CpuTypes": names(data.get("CpuTypes")),
            "GpuTypes": names(data.get("GpuTypes")),
            "HotBrands": [
                {"N": b.get("N"), "Name": b.get("Name")} for b in data.get("HotBrands") or []
            ],
        }
    items = data.get("RecommendItems") if tool == "product_recommend" else data.get("Items")
    out = {"Items": [slim_item(i) for i in (items or [])[:limit]]}
    if data.get("NumberOfItems") is not None:
        out["NumberOfItems"] = data["NumberOfItems"]
        out["Shown"] = len(out["Items"])
    if tool == "product_search":
        out["CpuTypes"] = names(data.get("CpuTypes"))
        out["GpuTypes"] = names(data.get("GpuTypes"))
        out["HotBrands"] = [
            {"N": b.get("N"), "Name": b.get("Name")} for b in data.get("HotBrands") or []
        ]
    return out


def die(message, code=2):
    print(f"pgg_api: {message}", file=sys.stderr)
    raise SystemExit(code)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    tool = argv[0]
    if tool not in METHODS:
        die(f"unknown tool {tool!r}; choose from {', '.join(METHODS)}", 1)

    raw = False
    limit = 20
    arguments = {"CountryCode": "USA", "CompanyCode": 1003}

    rest = argv[1:]
    index = 0
    while index < len(rest):
        token = rest[index]
        if token == "--raw":
            raw = True
        elif token == "--limit":
            index += 1
            limit = int(rest[index])
        elif token == "--country":
            index += 1
            arguments["CountryCode"] = rest[index]
        elif token == "--company":
            index += 1
            arguments["CompanyCode"] = int(rest[index])
        elif token == "--timeout":
            index += 1
            arguments["__timeout"] = int(rest[index])
        elif "=" in token:
            key, _, value = token.partition("=")
            arguments[key] = int(value) if key in INT_ARGS else value
        else:
            die(f"unrecognized argument {token!r} (expected Key=Value)", 1)
        index += 1

    timeout = arguments.pop("__timeout", 30)
    data = call(tool, arguments, timeout)
    view = data if raw else slim(tool, data, limit)
    print(json.dumps(view, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
