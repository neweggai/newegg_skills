#!/usr/bin/env python3
"""
Newegg PSU Wattage Calculator
Fetches CPU/GPU wattage from Newegg APIs, sums all components, recommends PSU tier.

Usage:
    python calculate_psu.py '<json_spec>'

Spec JSON fields (all optional except at least one component):
    cpu         - CPU model string, e.g. "Ryzen 7 9800X3D" or "i9-14900K"
    gpu         - GPU model string, e.g. "RTX 5080" or "RX 7900 XTX"
    gpu_count   - int, number of GPUs (default 1)
    mb          - motherboard form factor: "ATX"|"E-ATX"|"Micro ATX"|"Mini-ITX"|
                  "Thin Mini-ITX"|"SSI CEB"|"SSI EEB"|"XL AT"
                  (default "ATX", or "SSI CEB" when cpu looks like Threadripper/HEDT)
    ram         - RAM config string, e.g. "32GB DDR5" or "16GB DDR4"
    ram_count   - int, number of RAM sticks (default 1)
    ssd         - SSD size string, e.g. "1TB+" or "512GB" (default none)
    ssd_count   - int, number of SSDs (default 1)
    hdd         - HDD type string, e.g. "7200RPM 3.5\"" (default none)
    hdd_count   - int, number of HDDs (default 1)
    optical     - optical drive type: "Blu-Ray"|"DVD-RW"|"COMBO"|"CD-RW"|"DVD-ROM"|"CD-ROM"
                  (default none)
    skip_product_search - bool, set true to skip the live PSU product lookup
                  (recommended_products stays empty; shop_url is still returned)
    utm_source  - calling platform for Newegg link tagging, e.g. "claude",
                  "cursor", or "other" when undetermined (default
                  "other") -- see build_item_url() below and
                  newegg-pc-builder-v2's reference/product_link_rules.md for how
                  this is determined. Never hardcode a guess.

Example:
    python calculate_psu.py '{"cpu":"Ryzen 7 9800X3D","gpu":"RTX 5080","mb":"ATX","ram":"32GB DDR5","ram_count":2,"ssd":"1TB+"}'

Any unhandled error is caught at the top level and reported as {"error": ...} JSON —
never a raw Python traceback.
"""

import json
import re
import sys
import urllib.request
from difflib import SequenceMatcher

# --- Newegg link tagging (UTM) --------------------------------------------
# Same convention as newegg-pc-builder-v2's reference/product_link_rules.md.
# utm_source is the calling platform, resolved by the agent per
# environment_detection.md (Claude-exclusive tool present -> "claude", a
# Cursor project signature -> "cursor", etc.; "other" if undetermined)
# and passed in via the JSON spec's "utm_source" key -- never hardcode a guess.
UTM_CAMPAIGN_SLUG = "psu-calculator"
UTM_CONTENT = "newegg-psu-calculator"


def build_campaign(utm_source):
    """utm_campaign = aik_ + the platform used in utm_source + _<skill slug>."""
    return f"aik_{utm_source}_{UTM_CAMPAIGN_SLUG}"


def build_item_url(item_number, utm_source):
    """Tagged Newegg product-page link for a single item number."""
    utm_source = utm_source or "other"
    return (
        f"https://www.newegg.com/p/{item_number}?Item={item_number}"
        f"&utm_source={utm_source}&utm_medium=ai_skill"
        f"&utm_campaign={build_campaign(utm_source)}&utm_content={UTM_CONTENT}"
    )


def build_shop_url(recommended, utm_source):
    """Tagged Newegg category-search fallback link (no single Item=)."""
    utm_source = utm_source or "other"
    return (
        f"https://www.newegg.com/p/pl?d={recommended}W+PSU+modular+gold"
        f"&utm_source={utm_source}&utm_medium=ai_skill"
        f"&utm_campaign={build_campaign(utm_source)}&utm_content={UTM_CONTENT}"
    )


# Stage-4 GPU guess must beat this; equality is rejected (T400 vs "我没有 4090" == 0.50).
GPU_FUZZY_MIN_SIMILARITY = 0.5
# Below this similarity, a fixed-table lookup (motherboard) is treated as "not
# recognized" rather than silently taking the nearest (possibly nonsensical) match.
MB_FUZZY_MIN_SIMILARITY = 0.55
_CJK_RE = re.compile(r"[一-鿿]")
_GPU_NEGATION_RE = re.compile(
    r"(没有|沒有|不是|不要|别买|別買|don't|do not|\bnot\b|\bno\b)",
    re.IGNORECASE,
)
_HEDT_RE = re.compile(r"threadripper", re.IGNORECASE)


# ──────────────────────────────────────────────
# Fixed wattage tables
# ──────────────────────────────────────────────

MB_WATTS = {
    "atx": 70,
    "e-atx": 100,
    "micro atx": 60,
    "micro-atx": 60,
    "matx": 60,
    "mini-itx": 30,
    "mini itx": 30,
    "thin mini-itx": 20,
    "thin mini itx": 20,
    "ssi ceb": 150,
    "ssi eeb": 150,
    "xl at": 130,
}

RAM_WATTS = {
    "192gb ddr5": 57.6, "128gb ddr5": 38.4, "96gb ddr5": 28.8,
    "64gb ddr5": 19.2,  "48gb ddr5": 14.4,  "32gb ddr5": 9.6,
    "16gb ddr5": 4.8,   "8gb ddr5": 2.4,    "4gb ddr5": 1.2,
    "192gb ddr4": 72,   "128gb ddr4": 48,   "96gb ddr4": 36,
    "64gb ddr4": 24,    "48gb ddr4": 18,    "32gb ddr4": 12,
    "16gb ddr4": 6,     "8gb ddr4": 3,      "4gb ddr4": 1.5,
    "32gb ddr3": 6,     "8gb ddr3": 3,      "4gb ddr3": 2,
    "2gb ddr3": 1.5,
}

SSD_WATTS = {
    "under 120gb": 10, "120gb": 10, "120gb-256gb": 10, "256gb": 10,
    "256gb-512gb": 10, "512gb": 11, "512gb-1tb": 11, "1tb": 11, "1tb+": 11,
}

HDD_WATTS = {
    "5400rpm": 15, "5400": 15,
    "7200rpm": 20, "7200": 20,
    "10000rpm": 30, "10,000rpm": 30, "10k": 30,
    "15000rpm": 40, "15,000rpm": 40, "15k": 40,
}

OPTICAL_WATTS = {
    "blu-ray": 30, "blu ray": 30, "bluray": 30,
    "dvd-rw": 30, "dvd rw": 30,
    "combo": 24,
    "cd-rw": 16, "cd rw": 16,
    "dvd-rom": 20, "dvd rom": 20,
    "cd-rom": 15, "cd rom": 15,
}

PSU_TIERS = [550, 650, 750, 850, 1000, 1200, 1600]

# Wattage tables come from the www-tool MCP endpoint (stateless JSON-RPC, no auth).
MCP_ENDPOINT = "https://apis.newegg.com/ex-mcp/endpoint/website-www-tool"
CPU_WATTAGE_TOOL = "getapi_assistance_getJson_WWW_CPUWattage_USA"
GPU_WATTAGE_TOOL = "getapi_assistance_getJson_WWW_GPUWattage_USA"
COUNTRY_CODE = "USA"
COMPANY_CODE = 1003
# Identifies the calling skill to the endpoint; sent on every request.
SKILL_NAME = "newegg-psu-calculator"

# Live product search — used to attach 1-2 real PSU options (name/price/link) to
# the recommendation instead of only a generic category search link.
PRODUCT_SEARCH_ENDPOINT = "https://apis.newegg.com/ex-mcp/endpoint/product-search"
PRODUCT_SEARCH_TOOL = "newegg product search"
GOLD_OR_BETTER_RE = re.compile(
    r"80\s*\+?\s*plus\s*(gold|platinum|titanium)|80\s*plus\s*(gold|platinum|titanium)",
    re.IGNORECASE,
)
MAX_RECOMMENDED_PRODUCTS = 5


# ──────────────────────────────────────────────
# API helpers
# ──────────────────────────────────────────────

def _call_mcp_tool(endpoint, tool_name, arguments, timeout=15):
    """Generic JSON-RPC tools/call against one of the ex-mcp endpoints.

    Returns the parsed top-level envelope dict, or None on any failure.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    try:
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")

        # A streamable-http server may answer as SSE; take the last data: line.
        if raw.lstrip().startswith(("event:", "data:")):
            lines = [ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")]
            if not lines:
                return None
            raw = lines[-1]

        return json.loads(raw)
    except Exception:
        return None


def fetch_api(tool):
    """Fetch a wattage table through the www-tool MCP endpoint. Returns list of dicts.

    Returns [] on any failure — the caller turns that into a user-visible warning
    rather than a wrong wattage total.
    """
    envelope = _call_mcp_tool(
        MCP_ENDPOINT, tool, {"CountryCode": COUNTRY_CODE, "CompanyCode": COMPANY_CODE}
    )
    if not envelope:
        return []
    try:
        if envelope.get("error"):
            return []
        result = envelope.get("result") or {}
        if result.get("isError"):
            return []
        content = result.get("content") or []
        if not content:
            return []

        # The payload is multiply encoded: content[0].text is a JSON string that
        # decodes to another JSON string, then to {"Data": "<json list>"}.
        value = content[0]["text"]
        for _ in range(5):
            if isinstance(value, str):
                value = json.loads(value)
            elif isinstance(value, dict) and "Data" in value:
                value = value["Data"]
            else:
                break
        return value if isinstance(value, list) else []
    except Exception:
        return []


# The exact-wattage Gold+ match is frequently NOT on page 1 of a keyword search
# (e.g. a real 550W 80+ Gold unit can sit on page 2 while page 1 is dominated by
# higher-wattage or Bronze results) — verified by hand for the 550W tier. Scan a
# few pages before giving up, rather than reporting "nothing found" too early.
PSU_SEARCH_MAX_PAGES = 3


def fetch_psu_products(wattage_tier, utm_source="other"):
    """Look up 1-2 real 80+ Gold-or-better PSUs at the recommended wattage tier.

    Best-effort only: any failure (network, parsing, no Gold+ match after
    scanning a few pages) returns [] and the caller falls back to the generic
    shop_url — this must never raise and never block the wattage calculation.
    """
    query = f"{wattage_tier}W 80 PLUS Gold fully modular power supply"
    # Word-boundary match on the wattage: plain substring would let "1650W"
    # match a "650W" tier (found by testing — "650w" is literally inside
    # "1650w"). (?<!\d) blocks a preceding digit; \b blocks a following one
    # (so "6500W" doesn't match either).
    tier_re = re.compile(rf"(?<!\d){wattage_tier}w\b", re.IGNORECASE)
    picks = []
    seen_items = set()

    for page in range(1, PSU_SEARCH_MAX_PAGES + 1):
        envelope = _call_mcp_tool(
            PRODUCT_SEARCH_ENDPOINT,
            PRODUCT_SEARCH_TOOL,
            {"query": query, "order": 15, "page": page},  # order 15 = Best Selling
            timeout=15,
        )
        if not envelope:
            break
        try:
            if envelope.get("error"):
                break
            text = envelope["result"]["content"][0]["text"]
            data = json.loads(text)
            products = data.get("products") or []
        except Exception:
            break
        if not products:
            break

        for p in products:
            desc = p.get("WebDescription") or ""
            # Require an explicit 80+ Gold/Platinum/Titanium claim in the title —
            # a keyword search alone can surface Bronze units too; never present
            # a PSU as "recommended" without confirming certification from the
            # data actually returned.
            if not GOLD_OR_BETTER_RE.search(desc):
                continue
            # Require the wattage tier to appear in the title so we don't
            # recommend a 650W unit for an 850W tier just because it ranked
            # well — and don't let "1650W" false-match a "650W" tier either.
            if not tier_re.search(desc):
                continue
            item_number = p.get("ItemNumber")
            price = (p.get("Price") or {}).get("FinalPrice")
            currency = (p.get("Price") or {}).get("CurrencyCode", "USD")
            if not item_number or price is None:
                continue
            if item_number in seen_items:
                continue  # de-dupe across pages
            seen_items.add(item_number)
            picks.append({
                "name": desc,
                "item_number": item_number,
                "price": price,
                "currency": currency,
                "link": build_item_url(item_number, utm_source),
            })
            if len(picks) >= MAX_RECOMMENDED_PRODUCTS:
                return picks

        if len(products) < 10:
            # Short page — unlikely more relevant results follow.
            break

    return picks


def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def allow_gpu_stage4_similarity(query):
    """Refuse last-resort similarity guesses for sentence-like GPU strings.

    Model tokens (RTX 5080, 4090, GT 730) still match on stages 1-3.
    Prose such as "我没有 4090" must not pick a random short SKU (T400).
    """
    q = (query or "").strip()
    if not q:
        return False
    if _CJK_RE.search(q):
        return False
    if _GPU_NEGATION_RE.search(q):
        return False
    return True


def is_no_discrete_gpu(query):
    """True for explicit iGPU / no add-in GPU phrases (auxiliary filter)."""
    if query is None:
        return True
    q = str(query).lower().strip()
    if not q:
        return True
    compact = " ".join("".join(ch if ch.isalnum() or ch.isspace() else " " for ch in q).split())
    exact = {
        "no discrete gpu",
        "no discrete graphics",
        "no dedicated gpu",
        "no dedicated graphics",
        "integrated graphics",
        "integrated gpu",
        "integrated",
        "onboard graphics",
        "igpu",
        "none",
        "n/a",
        "na",
        "null",
        "not decided yet",
        "undecided",
        "无独显",
        "没有独显",
        "無獨顯",
        "核显",
        "核顯",
        "内显",
        "內显",
    }
    if compact in exact or q in exact:
        return True
    markers = (
        "no discrete",
        "no dedicated",
        "integrated graphic",
        "integrated gpu",
        "onboard graphic",
        "not decided",
        "核显",
        "核顯",
        "无独显",
        "無獨顯",
        "没有独显",
        "沒有獨顯",
    )
    return any(m in q for m in markers)


def is_hedt_cpu(query):
    """True when the CPU string looks like Threadripper / HEDT."""
    return bool(query) and bool(_HEDT_RE.search(str(query)))


def fuzzy_match(query, candidates, key, min_similarity=None, allow_similarity_fallback=True):
    """Find best matching item in candidates list by key field.

    Thin wrapper over fuzzy_match_detailed() for callers that only need the
    item itself.
    """
    item, _stage, _score = fuzzy_match_detailed(
        query, candidates, key, min_similarity, allow_similarity_fallback
    )
    return item


def fuzzy_match_detailed(query, candidates, key, min_similarity=None,
                         allow_similarity_fallback=True):
    """fuzzy_match() plus how the hit was reached: (item, stage, score).

    Priority:
    1. Exact case-insensitive match on the key field
    2. Query is a suffix/prefix-boundary match (avoids "7950X" -> "7950X3D")
    3. All query words appear in the candidate, prefer shorter candidate names
    4. Highest character similarity (optional; GPU uses a floor and may skip)

    Stages 1-3 all require the query's own words to be present, so they are
    confident hits. Stage 4 is the only one that returns a nearest neighbour
    the caller never named -- it reports stage 4 with its similarity score so
    the caller can warn instead of passing the guess off as a real match.
    A miss is (None, None, 0.0).
    """
    q = query.lower().strip()
    q_words = q.split()

    # 1. Exact match
    for item in candidates:
        if item[key].lower() == q:
            return item, 1, 1.0

    # 2. Boundary-aware substring: each query word must appear as a whole word
    #    or at the end of the string (prevents "7950X" matching "7950X3D")
    def all_words_boundary(q_words, text):
        text = text.lower()
        for w in q_words:
            # word must be at boundary: preceded/followed by non-alphanumeric or end
            if not re.search(r'(?<![a-z0-9])' + re.escape(w) + r'(?![a-z0-9])', text):
                return False
        return True

    boundary_hits = [item for item in candidates if all_words_boundary(q_words, item[key])]
    if boundary_hits:
        # Among boundary hits, prefer the one with shortest name (most specific match)
        best = min(boundary_hits, key=lambda x: len(x[key]))
        return best, 2, similarity(q, best[key].lower())

    # 3. All words appear anywhere (fallback)
    word_hits = [
        item for item in candidates
        if all(w in item[key].lower() for w in q_words)
    ]
    if word_hits:
        best = min(word_hits, key=lambda x: abs(len(x[key]) - len(q)))
        return best, 3, similarity(q, best[key].lower())

    # 4. Best similarity score (GPU: skip prose; require score strictly above floor)
    if not allow_similarity_fallback or not candidates:
        return None, None, 0.0
    best = max(candidates, key=lambda x: similarity(q, x[key].lower()))
    score = similarity(q, best[key].lower())
    if min_similarity is not None and score <= min_similarity:
        return None, None, score
    return best, 4, score


def parse_watts(w_str):
    """Parse '170W' -> 170"""
    try:
        return float(w_str.replace("W", "").replace("w", "").strip())
    except Exception:
        return 0.0


def safe_int(value, default=1):
    """Best-effort int conversion. Returns (value, ok) — never raises.

    A malformed count (e.g. gpu_count sent as prose) falls back to `default`
    with ok=False, so the caller can add a warning instead of crashing.
    """
    try:
        return int(value), True
    except (TypeError, ValueError):
        return default, False


# ──────────────────────────────────────────────
# Component lookup helpers
#
# Design rule: every lookup below either returns a confident match, or None —
# never a silently-guessed nearest neighbor and never a bare numeric default
# with no trace in warnings[]. The caller is responsible for turning a None
# into an explicit warning plus a stated fallback.
# ──────────────────────────────────────────────

def lookup_cpu(query, cpu_list):
    match = fuzzy_match(query, cpu_list, "Series")
    if match:
        return match["Series"], parse_watts(match["Wattage"])
    return None, 0.0


def lookup_gpu(query, gpu_list):
    """Returns (name, watts, approx_score).

    approx_score is None for a confident hit (the query's own words are in the
    matched name) and the similarity score when the match came from the
    nearest-neighbour stage -- i.e. a card the user never actually named. The
    caller turns that score into a warning rather than reporting the guess as
    a plain match.
    """
    match, stage, score = fuzzy_match_detailed(
        query,
        gpu_list,
        "GPU",
        min_similarity=GPU_FUZZY_MIN_SIMILARITY,
        allow_similarity_fallback=allow_gpu_stage4_similarity(query),
    )
    if match:
        approx = score if stage == 4 else None
        return match["GPU"], parse_watts(match["Wattage"]), approx
    return None, 0.0, None


def lookup_mb(mb_str):
    """Returns watts, or None if the string doesn't confidently match a known
    form factor (caller decides the fallback and records a warning)."""
    key = mb_str.lower().strip()
    if key in MB_WATTS:
        return MB_WATTS[key]
    best_k = max(MB_WATTS.keys(), key=lambda k: similarity(key, k))
    if similarity(key, best_k) < MB_FUZZY_MIN_SIMILARITY:
        return None
    return MB_WATTS[best_k]


def lookup_ram(ram_str):
    """Returns watts, or None if unrecognized (caller warns; not counted)."""
    key = ram_str.lower().strip()
    if key in RAM_WATTS:
        return RAM_WATTS[key]
    for k, v in RAM_WATTS.items():
        if k in key or key in k:
            return v
    return None


def lookup_ssd(ssd_str):
    """Returns watts, or None if unrecognized (caller warns and may still
    apply a stated default so an SSD isn't silently dropped from the total)."""
    key = ssd_str.lower().replace(" ", "").strip()
    for k, v in SSD_WATTS.items():
        if k.replace("-", "").replace(" ", "") in key or key in k.replace("-", "").replace(" ", ""):
            return v
    return None


def lookup_hdd(hdd_str):
    """Returns watts, or None if unrecognized (caller warns and may still
    apply a stated default)."""
    key = hdd_str.lower().replace(",", "").replace(" ", "")
    for k, v in HDD_WATTS.items():
        if k.replace(",", "").replace(" ", "") in key:
            return v
    return None


def lookup_optical(optical_str):
    key = optical_str.lower().strip()
    for k, v in OPTICAL_WATTS.items():
        if k in key or key in k:
            return v
    return None


def recommend_psu(total_watts):
    """Round up to next standard PSU tier with ~20% headroom.

    Returns (recommended_tier, headroom_target_watts).
    """
    target = total_watts * 1.2
    for tier in PSU_TIERS:
        if tier >= target:
            return tier, target
    return PSU_TIERS[-1], target


def next_psu_tier(recommended_watts):
    """Next catalog tier above the main recommendation, or None."""
    for tier in PSU_TIERS:
        if tier > recommended_watts:
            return tier
    return None


def build_recommendation_note(total_watts, headroom_watts, recommended, floor_applied):
    """Agent-facing note for Phase 3 wording (D14/D15)."""
    live_data_caveat = (
        " CPU/GPU wattages come from Newegg's live product tables and can shift "
        "slightly between queries as the catalog updates — treat the tier as "
        "current-best-estimate, not a permanently fixed number."
    )
    if floor_applied:
        return (
            f"System draw {total_watts}W; after x1.2 headroom ~{headroom_watts}W, "
            f"still below the 550W catalog floor. Main recommendation is 550W as the "
            f"starting purchase tier (modular Gold availability)—not because the build "
            f"needs ~550W continuous, and not because 550W equals the 20% margin alone. "
            f"Users may pick a lower-wattage PSU on their own; the shop link stays at "
            f"550W.{live_data_caveat}"
        )
    return (
        f"System draw {total_watts}W; after x1.2 headroom ~{headroom_watts}W, "
        f"rounded up to the next catalog tier {recommended}W. "
        f"Main recommendation and first shop link must both be "
        f"{recommended}W.{live_data_caveat}"
    )


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def _run(spec):
    # Calling platform for link tagging -- see build_item_url/build_shop_url above.
    # Passed by the agent in the JSON spec; defaults to "other" if omitted.
    utm_source = spec.get("utm_source") or "other"
    result = {
        "components": [],
        "total_watts": 0.0,
        "headroom_watts": 0.0,
        "recommended_psu_watts": 0,
        "catalog_floor_applied": False,
        "optional_higher_tier_watts": None,
        "recommendation_note": "",
        "shop_url": "",
        "recommended_products": [],
        "warnings": [],
    }
    total = 0.0
    hedt = is_hedt_cpu(spec.get("cpu"))

    # ── CPU ──
    if spec.get("cpu"):
        cpu_list = fetch_api(CPU_WATTAGE_TOOL)
        if not cpu_list:
            result["warnings"].append("Could not fetch CPU data from API; CPU wattage not included.")
        else:
            name, watts = lookup_cpu(spec["cpu"], cpu_list)
            if name:
                total += watts
                result["components"].append({"type": "CPU", "name": name, "watts": watts})
            else:
                result["warnings"].append(f"CPU '{spec['cpu']}' not found in API data.")

    # ── GPU ──
    # Auxiliary: known iGPU / no-dGPU phrases => 0W (do not fuzzy-match).
    # Stage-4: skip sentence-like queries; refuse similarity <= 0.5 (T400 / 我没有 4090).
    gpu_raw = spec.get("gpu")
    gpu_count, gpu_count_ok = safe_int(spec.get("gpu_count", 1), default=1)
    if not gpu_count_ok:
        result["warnings"].append(
            f"gpu_count '{spec.get('gpu_count')}' is not a number; assumed 1."
        )
    if gpu_raw is not None and str(gpu_raw).strip() and is_no_discrete_gpu(gpu_raw):
        result["components"].append({
            "type": "GPU",
            "name": "No discrete GPU (iGPU)",
            "watts": 0.0,
            "count": 1,
            "subtotal": 0.0,
        })
    elif gpu_raw is not None and str(gpu_raw).strip():
        gpu_list = fetch_api(GPU_WATTAGE_TOOL)
        if not gpu_list:
            result["warnings"].append("Could not fetch GPU data from API; GPU wattage not included.")
        else:
            name, watts, approx_score = lookup_gpu(gpu_raw, gpu_list)
            if name:
                total += watts * gpu_count
                component = {
                    "type": "GPU", "name": name, "watts": watts,
                    "count": gpu_count, "subtotal": watts * gpu_count
                }
                if approx_score is not None:
                    component["approximate_match"] = True
                    component["match_similarity"] = round(approx_score, 2)
                    result["warnings"].append(
                        f"GPU '{gpu_raw}' has no exact entry in Newegg's wattage "
                        f"table; used the closest one, '{name}' ({watts:g}W, "
                        f"similarity {approx_score:.2f}). Confirm this is the "
                        f"intended card — a different model changes the "
                        f"recommended PSU tier."
                    )
                result["components"].append(component)
            else:
                result["warnings"].append(
                    f"GPU '{gpu_raw}' not found or low-confidence match ignored; "
                    f"GPU wattage not included."
                )

    # ── Motherboard ──
    # Default form factor is ATX, EXCEPT a Threadripper/HEDT CPU with no
    # explicit mb — those default to SSI CEB (150W), not ATX (70W), because a
    # HEDT board is never a plain consumer ATX board in practice.
    mb_raw = spec.get("mb")
    mb_defaulted = not (mb_raw is not None and str(mb_raw).strip())
    if mb_defaulted:
        mb = "SSI CEB" if hedt else "ATX"
        mb_watts = MB_WATTS[mb.lower()]
        mb_name = f"{mb} (default{', HEDT/Threadripper' if hedt else ''})"
    else:
        mb = str(mb_raw).strip()
        mb_watts = lookup_mb(mb)
        if mb_watts is None:
            fallback = "SSI CEB" if hedt else "ATX"
            mb_watts = MB_WATTS[fallback.lower()]
            result["warnings"].append(
                f"Motherboard '{mb_raw}' not recognized; assumed {fallback} "
                f"({mb_watts}W) as a fallback — verify the actual form factor."
            )
            mb_name = f"{mb_raw} (unrecognized, assumed {fallback})"
        else:
            mb_name = mb
    total += mb_watts
    result["components"].append({"type": "Motherboard", "name": mb_name, "watts": mb_watts})

    # ── RAM ──
    if spec.get("ram"):
        ram_watts = lookup_ram(spec["ram"])
        qty, qty_ok = safe_int(spec.get("ram_count", 1), default=1)
        if not qty_ok:
            result["warnings"].append(f"ram_count '{spec.get('ram_count')}' is not a number; assumed 1.")
        if ram_watts is None:
            result["warnings"].append(
                f"RAM '{spec['ram']}' not recognized; RAM wattage NOT included in the total "
                f"(this will understate the recommendation — ask the user to confirm capacity/type)."
            )
            result["components"].append({
                "type": "RAM", "name": f"{spec['ram']} (unrecognized, not counted)",
                "watts": 0.0, "count": qty, "subtotal": 0.0
            })
        else:
            total += ram_watts * qty
            result["components"].append({
                "type": "RAM", "name": spec["ram"], "watts": ram_watts,
                "count": qty, "subtotal": ram_watts * qty
            })

    # ── SSD ──
    if spec.get("ssd"):
        ssd_watts = lookup_ssd(spec["ssd"])
        qty, qty_ok = safe_int(spec.get("ssd_count", 1), default=1)
        if not qty_ok:
            result["warnings"].append(f"ssd_count '{spec.get('ssd_count')}' is not a number; assumed 1.")
        if ssd_watts is None:
            ssd_watts = 11.0  # stated fallback: 512GB-1TB+ tier, the common case
            result["warnings"].append(
                f"SSD '{spec['ssd']}' not recognized; assumed {ssd_watts}W "
                f"(512GB-1TB tier) as a fallback."
            )
        total += ssd_watts * qty
        result["components"].append({
            "type": "SSD", "name": spec["ssd"], "watts": ssd_watts,
            "count": qty, "subtotal": ssd_watts * qty
        })

    # ── HDD ──
    if spec.get("hdd"):
        hdd_watts = lookup_hdd(spec["hdd"])
        qty, qty_ok = safe_int(spec.get("hdd_count", 1), default=1)
        if not qty_ok:
            result["warnings"].append(f"hdd_count '{spec.get('hdd_count')}' is not a number; assumed 1.")
        if hdd_watts is None:
            hdd_watts = 20.0  # stated fallback: 7200RPM tier, the common case
            result["warnings"].append(
                f"HDD '{spec['hdd']}' not recognized; assumed {hdd_watts}W "
                f"(7200RPM tier) as a fallback."
            )
        total += hdd_watts * qty
        result["components"].append({
            "type": "HDD", "name": spec["hdd"], "watts": hdd_watts,
            "count": qty, "subtotal": hdd_watts * qty
        })

    # ── Optical ──
    if spec.get("optical"):
        opt_watts = lookup_optical(spec["optical"])
        if opt_watts is None:
            opt_watts = 20.0  # stated fallback: DVD-ROM tier
            result["warnings"].append(
                f"Optical drive '{spec['optical']}' not recognized; assumed {opt_watts}W as a fallback."
            )
        total += opt_watts
        result["components"].append({
            "type": "Optical", "name": spec["optical"], "watts": opt_watts
        })

    total = round(total, 1)
    recommended, headroom = recommend_psu(total)
    headroom = round(headroom, 1)
    floor_applied = recommended == PSU_TIERS[0] and headroom < PSU_TIERS[0]
    higher = next_psu_tier(recommended)

    result["total_watts"] = total
    result["headroom_watts"] = headroom
    result["recommended_psu_watts"] = recommended
    result["catalog_floor_applied"] = floor_applied
    result["optional_higher_tier_watts"] = higher
    result["recommendation_note"] = build_recommendation_note(
        total, headroom, recommended, floor_applied
    )
    result["shop_url"] = build_shop_url(recommended, utm_source)

    if not spec.get("skip_product_search"):
        try:
            result["recommended_products"] = fetch_psu_products(recommended, utm_source)
        except Exception:
            # Never let the product-lookup enhancement break the core calculation.
            result["recommended_products"] = []

    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: calculate_psu.py '<json_spec>'"}))
        sys.exit(1)

    try:
        spec = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON spec: {e}"}))
        sys.exit(1)

    # Top-level safety net: any unforeseen bug below must surface as clean JSON,
    # never a raw traceback dumped to the user.
    try:
        result = _run(spec)
    except Exception as e:
        print(json.dumps({"error": f"Internal error while calculating PSU wattage: {e}"}))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
