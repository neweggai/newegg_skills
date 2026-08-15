#!/usr/bin/env python3
"""Newegg product search - direct API client for the monitor finder (no MCP required).

The product-search endpoint speaks stateless JSON-RPC over plain HTTPS, so any agent
with a shell can call it without an MCP server configured. This client also parses the
per-product spec HTML and slims the response, which is what keeps monitor results
readable in context.

The query must be an ENGLISH search term. The catalog is indexed in English only, so a
non-English query returns zero results rather than an error - this client rejects any
query with a non-ASCII character up front, instead of letting it look like "no monitors
matched".

Usage:
    python monitor_api.py "144Hz gaming monitor"
    python monitor_api.py "OLED gaming monitor" --max-price 900 --order 15
    python monitor_api.py "curved ultrawide gaming monitor" --min-price 350 --max-price 800 --limit 30
    python monitor_api.py "240Hz gaming monitor" --page 2

Options:
    --min-price N   minimum price (inclusive)
    --max-price N   maximum price (inclusive)
    --order N       sort: 15 best selling (default), 1 best rating, 2 lowest price,
                    3 highest price, 4 most reviews, 8 featured
    --page N        1-based page number (default 1)
    --limit N       max items to print (default 30; slim mode only)
    --raw           print the full upstream JSON instead of the slimmed view
    --timeout N     seconds (default 30)

Exit codes: 0 ok, 1 usage error, 2 transport/API error.
"""

import json
import re
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://apis.newegg.com/ex-mcp/endpoint/product-search"
TOOL = "newegg product search"
# Identifies the calling skill to the endpoint; sent on every request.
SKILL_NAME = "newegg-monitor-finder"

SPEC_RE = re.compile(r"<b>(.*?):</b>\s*([^<]*)")
SIZE_RE = re.compile(r"([\d.]+)")
SYNC_RE = re.compile(
    r"\b(G-?Sync|FreeSync)(\s+Premium)?(\s+Pro)?(\s+Compatible)?", re.IGNORECASE
)
# The catalog has no non-English index, so such a query silently returns 0. Any
# non-ASCII character means the query was not translated - CJK, Cyrillic, accented
# Latin alike. An English search term is plain ASCII.
NON_ASCII_RE = re.compile(r"[^\x00-\x7f]")

# Spec labels kept in the slim view, in display order.
SPEC_KEYS = (
    "Screen Size",
    "Resolution",
    "Refresh Rate",
    "Response Time",
    "Panel",
    "Aspect Ratio",
    "Curved Surface Screen",
    "Display Colors",
)


def die(message, code=2):
    print(f"monitor_api: {message}", file=sys.stderr)
    raise SystemExit(code)


def call(arguments, timeout=30):
    """POST one JSON-RPC tools/call and return the decoded payload dict."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": TOOL, "arguments": arguments},
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
    except urllib.error.HTTPError as exc:
        die(f"HTTP {exc.code} from product search API: "
            f"{exc.read().decode('utf-8', 'replace')[:400]}")
    except urllib.error.URLError as exc:
        die(f"cannot reach product search API: {exc.reason}")

    # A streamable-http server may answer as SSE; take the last data: line.
    if body.lstrip().startswith(("event:", "data:")):
        data_lines = [ln[5:].strip() for ln in body.splitlines() if ln.startswith("data:")]
        if not data_lines:
            die("empty SSE response from product search API")
        body = data_lines[-1]

    envelope = json.loads(body)
    # Truthiness, not key presence: some JSON-RPC servers send an explicit "error": null
    # alongside a perfectly good result.
    if envelope.get("error"):
        die(f"product search API error: {json.dumps(envelope['error'])[:400]}")
    result = envelope.get("result") or {}
    if result.get("isError"):
        die(f"product search API returned isError: {json.dumps(result)[:400]}")
    if isinstance(result.get("structuredContent"), dict) and "products" in result["structuredContent"]:
        return result["structuredContent"]
    content = result.get("content") or []
    if not content:
        die("product search API returned no content")
    return json.loads(content[0]["text"])


def parse_specs(view_description):
    """Turn the ViewDescription HTML fragment into a {label: value} dict."""
    if not view_description:
        return {}
    return {k.strip(): v.strip() for k, v in SPEC_RE.findall(view_description)}


def size_inches(specs):
    """Numeric screen size, for local size filtering. None when unparseable."""
    match = SIZE_RE.search(specs.get("Screen Size", ""))
    return float(match.group(1)) if match else None


def haystack_of(product, specs):
    return " ".join(
        filter(None, [product.get("WebDescription"), product.get("BulletDescription"),
                      specs.get("G-SYNC"), specs.get("Adaptive Sync")])
    )


def adaptive_sync(haystack):
    """G-Sync / FreeSync support - more reliably present in the title than in specs.

    A title routinely names one family more than once ("...FreeSync Premium Pro & G-Sync
    Compatible... AMD FreeSync"), so keep only the most specific variant per family.
    Emitting both "G-Sync" and "G-Sync Compatible" would read as two separate features
    and claim a native G-Sync module the product does not have.
    """
    best = {}
    for match in SYNC_RE.finditer(haystack):
        family = "G-Sync" if match.group(1).lower().startswith("g") else "FreeSync"
        parts = [family] + [g.strip().title() for g in match.groups()[1:] if g]
        label = " ".join(parts)
        if len(label) > len(best.get(family, "")):
            best[family] = label
    return sorted(best.values()) or None


def is_curved(specs, haystack):
    """Curved flag - the spec field is often absent, so fall back to the title."""
    curved = specs.get("Curved Surface Screen")
    if curved:
        return curved.strip().lower() == "curved"
    if re.search(r"\bcurved\b", haystack, re.IGNORECASE):
        return True
    return None


def slim_product(product):
    specs = parse_specs(product.get("ViewDescription"))
    price = product.get("Price") or {}
    number = product.get("ItemNumber")
    haystack = haystack_of(product, specs)
    out = {
        "ItemNumber": number,
        "Url": f"https://www.newegg.com/p/{number}" if number else None,
        "Title": product.get("WebDescription"),
        "FinalPrice": price.get("FinalPrice"),
        "PriceSaveText": price.get("PriceSaveText") or None,
        "Rating": price.get("RatingOneDecimal"),
        "Reviews": price.get("HumanRating"),
        "IsRefurbished": product.get("IsRefurbished") or None,
        "SizeInches": size_inches(specs),
        "IsCurved": is_curved(specs, haystack),
        "AdaptiveSync": adaptive_sync(haystack),
    }
    out.update({key: specs.get(key) for key in SPEC_KEYS})
    # Drop empty fields: unknown specs read as absent, and it keeps the payload small.
    return {k: v for k, v in out.items() if v is not None}


def slim(data, limit):
    products = data.get("products") or []
    return {
        "total": data.get("total"),
        "page": data.get("page"),
        "pageSize": data.get("pageSize"),
        "totalPage": data.get("totalPage"),
        "shown": min(len(products), limit),
        "products": [slim_product(p) for p in products[:limit]],
    }


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    query = None
    raw = False
    limit = 30
    timeout = 30
    arguments = {"order": 15, "page": 1}

    def value_after(token, index, cast):
        """Read an option's value, as a usage error rather than a traceback."""
        if index >= len(argv):
            die(f"{token} needs a value", 1)
        try:
            return cast(argv[index])
        except ValueError:
            die(f"{token} needs a number; got {argv[index]!r}", 1)

    index = 0
    while index < len(argv):
        token = argv[index]
        if token in ("--min-price", "--max-price"):
            index += 1
            key = "minPrice" if token == "--min-price" else "maxPrice"
            arguments[key] = value_after(token, index, float)
        elif token in ("--order", "--page"):
            index += 1
            arguments[token.lstrip("-")] = value_after(token, index, int)
        elif token == "--limit":
            index += 1
            limit = value_after(token, index, int)
        elif token == "--timeout":
            index += 1
            timeout = value_after(token, index, int)
        elif token == "--raw":
            raw = True
        elif token.startswith("--"):
            die(f"unknown option {token!r}", 1)
        elif query is None:
            query = token
        else:
            die(f"unexpected argument {token!r} (quote the query as one argument)", 1)
        index += 1

    if not query:
        die("missing search query", 1)
    if NON_ASCII_RE.search(query):
        # ASCII-only message: a console on a legacy codepage would mangle CJK examples.
        die(
            "the query is not English. The catalog is indexed in English only, so this "
            "returns zero results, which is indistinguishable from 'nothing in stock'. "
            "Translate the user's request into an English search term first, e.g. "
            '"gaming monitor" / "144Hz gaming monitor" / "curved ultrawide gaming '
            'monitor" -- see the query table in SKILL.md Step 2.',
            1,
        )
    arguments["query"] = query

    # Out-of-range values are accepted by the API and come back as an empty result set,
    # which reads like "no matches" - reject them here so the mistake is visible.
    if arguments["page"] < 1:
        die(f"--page must be 1-based; got {arguments['page']}", 1)
    if limit < 1:
        die(f"--limit must be at least 1; got {limit}", 1)
    for flag, key in (("--min-price", "minPrice"), ("--max-price", "maxPrice")):
        if arguments.get(key) is not None and arguments[key] < 0:
            die(f"{flag} must not be negative; got {arguments[key]}", 1)
    low, high = arguments.get("minPrice"), arguments.get("maxPrice")
    if low is not None and high is not None and low > high:
        die(f"--min-price {low} is above --max-price {high}", 1)

    data = call(arguments, timeout)
    view = data if raw else slim(data, limit)
    print(json.dumps(view, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
