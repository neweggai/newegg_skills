#!/usr/bin/env python3
"""
Newegg PC Builder compatibility client.

Why this script exists instead of a raw curl in SKILL.md: the ex-mcp gateway
attaches a `_meta.httpRequest` block to every response that echoes back internal
infrastructure detail (`x-gateway-server`, `x-forwarded-for`, `x-origin-host`,
the upstream apis.newegg.org URL) together with the caller's own public IP
(`true-client-ip`). A raw curl drops all of that into the conversation, where it
is then forwarded to whichever model provider is running the skill. Every
command here prints only the verdict payload; `_meta` never leaves the process.

Usage:
    python pcb_client.py verify <item> [<item> ...]
    python pcb_client.py check  <item> [<item> ...]
    python pcb_client.py search "<keyword>"

`check` verifies every item number against the catalog before submitting the
combo, because comboCompatibleAll does not validate item numbers: a typo'd or
hallucinated number is treated as "no data" and comes back `isCompatible: true`,
indistinguishable from a genuine pass.

All errors are reported as {"error": ...} JSON, never a raw traceback.
"""

import sys
import json
import urllib.request
import urllib.error

PCB_ENDPOINT = "https://apis.newegg.com/ex-mcp/endpoint/ext-pc-builder"
SEARCH_ENDPOINT = "https://apis.newegg.com/ex-mcp/endpoint/product-search"
SEARCH_TOOL = "newegg product search"
SKILL_NAME = "newegg-pc-compatibility-checker"
BUSINESS_ID = 2
COUNTRY_CODE = "USA"
# Must be the numeric company code; the string "Newegg" makes the upstream
# service answer 400 NumberFormatException.
COMPANY_CODE = 1003
TIMEOUT = 60

# Emoji and CJK in API payloads crash on a GBK/cp936 console (Windows zh-CN).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _call(endpoint, tool, arguments):
    """JSON-RPC tools/call. Returns the tool payload, with `_meta` discarded."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "x-skill": SKILL_NAME,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} from {endpoint}: {body[:300]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach {endpoint}: {e.reason}") from e

    # A streamable-http server may answer as SSE; take the last data: line.
    if raw.lstrip().startswith(("event:", "data:")):
        lines = [ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")]
        if not lines:
            raise RuntimeError("Empty SSE stream from the endpoint.")
        raw = lines[-1]

    envelope = json.loads(raw)
    if envelope.get("error"):
        raise RuntimeError(f"MCP error: {envelope['error']}")

    # Read only the fields the skill needs. `result._meta` is deliberately never
    # touched — that is the whole point of this wrapper.
    result = envelope.get("result") or {}
    if result.get("isError"):
        raise RuntimeError(f"Tool reported an error: {result.get('content')}")

    structured = result.get("structuredContent")
    if structured is not None:
        return structured
    content = result.get("content") or []
    if not content:
        raise RuntimeError("Endpoint returned no content.")
    text = content[0].get("text", "")
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"text": text}


def search(keyword):
    return _call(SEARCH_ENDPOINT, SEARCH_TOOL, {"query": keyword, "page": 1})


def verify_items(items):
    """Confirm each item number exists in Newegg's catalog.

    Existence is decided by `getWattageInfo`, pc-builder's own catalog lookup:
    it echoes back one entry per item number it knows and silently omits the
    rest, so an omission is a definitive "not in the catalog". product-search is
    deliberately NOT used for this — it is a keyword search, not an exact-ID
    lookup, and real item numbers routinely fail to surface on page 1 (verified:
    19-113-787 is a live product that a keyword search for its own number does
    not return). Using it as the gate would reject valid builds.

    product-search is still called afterwards, best-effort, purely to attach a
    display name and price; a miss there never blocks the check.
    """
    known = set()
    try:
        data = _call(
            PCB_ENDPOINT,
            "getWattageInfo",
            {"itemNumber": " ".join(items), "country": COUNTRY_CODE, "company": COMPANY_CODE},
        )
        known = {e.get("itemNumber") for e in (data.get("items") or [])}
    except Exception as e:
        raise RuntimeError(f"Could not verify item numbers against the catalog: {e}") from e

    found, missing = {}, []
    for item in items:
        if item not in known:
            missing.append({"itemNumber": item, "reason": "not found in Newegg's catalog"})
            continue
        entry = {"itemNumber": item, "url": f"https://www.newegg.com/p/{item}"}
        try:
            products = (search(item).get("products") or [])
            hit = next((x for x in products if x.get("ItemNumber") == item), None)
            if hit:
                price = hit.get("Price") or {}
                entry["description"] = hit.get("WebDescription")
                entry["price"] = price.get("FinalPrice")
                entry["currency"] = price.get("CurrencyCode")
        except Exception:
            pass  # Enrichment only — never let it fail the verification.
        found[item] = entry
    return found, missing


def cmd_verify(items):
    found, missing = verify_items(items)
    return {"verified": list(found.values()), "not_found": missing}


def cmd_check(items):
    found, missing = verify_items(items)
    if missing:
        return {
            "error": (
                "Refusing to run the compatibility check: one or more item numbers "
                "are not in Newegg's catalog. pc-builder treats an unknown item as "
                "'no data' and would return isCompatible: true, which looks exactly "
                "like a genuine pass. Resolve these with the user first."
            ),
            "not_found": missing,
            "verified": list(found.values()),
        }
    verdict = _call(
        PCB_ENDPOINT,
        "comboCompatibleAll",
        {"businessId": BUSINESS_ID, "itemNumber": " ".join(items)},
    )
    return {"items": list(found.values()), "verdict": verdict}


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": __doc__.split("Usage:")[1].strip()}))
        sys.exit(1)
    command, args = sys.argv[1], sys.argv[2:]
    try:
        if command == "verify":
            out = cmd_verify(args)
        elif command == "check":
            if len(args) < 2:
                raise ValueError("check needs at least two item numbers.")
            out = cmd_check(args)
        elif command == "search":
            out = search(" ".join(args))
        else:
            raise ValueError(f"Unknown command '{command}'. Use verify, check or search.")
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
