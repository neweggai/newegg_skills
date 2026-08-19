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
                  "Thin Mini-ITX"|"SSI CEB"|"SSI EEB"|"XL AT"  (default "ATX")
    ram         - RAM config string, e.g. "32GB DDR5" or "16GB DDR4"
    ram_count   - int, number of RAM sticks (default 1)
    ssd         - SSD size string, e.g. "1TB+" or "512GB" (default none)
    ssd_count   - int, number of SSDs (default 1)
    hdd         - HDD type string, e.g. "7200RPM 3.5\"" (default none)
    hdd_count   - int, number of HDDs (default 1)
    optical     - optical drive type: "Blu-Ray"|"DVD-RW"|"COMBO"|"CD-RW"|"DVD-ROM"|"CD-ROM"
                  (default none)

Example:
    python calculate_psu.py '{"cpu":"Ryzen 7 9800X3D","gpu":"RTX 5080","mb":"ATX","ram":"32GB DDR5","ram_count":2,"ssd":"1TB+"}'
"""

import json
import re
import sys
import urllib.request
from difflib import SequenceMatcher

# Stage-4 GPU guess must beat this; equality is rejected (T400 vs "我没有 4090" == 0.50).
GPU_FUZZY_MIN_SIMILARITY = 0.5
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_GPU_NEGATION_RE = re.compile(
    r"(没有|沒有|不是|不要|别买|別買|don't|do not|\bnot\b|\bno\b)",
    re.IGNORECASE,
)


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


# ──────────────────────────────────────────────
# API helpers
# ──────────────────────────────────────────────

def fetch_api(tool):
    """Fetch a wattage table through the www-tool MCP endpoint. Returns list of dicts.

    Returns [] on any failure — the caller turns that into a user-visible warning
    rather than a wrong wattage total.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool,
            "arguments": {"CountryCode": COUNTRY_CODE, "CompanyCode": COMPANY_CODE},
        },
    }
    try:
        req = urllib.request.Request(
            MCP_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "x-skill": SKILL_NAME,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")

        # A streamable-http server may answer as SSE; take the last data: line.
        if raw.lstrip().startswith(("event:", "data:")):
            lines = [ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")]
            if not lines:
                return []
            raw = lines[-1]

        envelope = json.loads(raw)
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
        "內顯",
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


def fuzzy_match(query, candidates, key, min_similarity=None, allow_similarity_fallback=True):
    """Find best matching item in candidates list by key field.

    Priority:
    1. Exact case-insensitive match on the key field
    2. Query is a suffix/prefix-boundary match (avoids "7950X" -> "7950X3D")
    3. All query words appear in the candidate, prefer shorter candidate names
    4. Highest character similarity (optional; GPU uses a floor and may skip)
    """
    q = query.lower().strip()
    q_words = q.split()

    # 1. Exact match
    for item in candidates:
        if item[key].lower() == q:
            return item

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
        return min(boundary_hits, key=lambda x: len(x[key]))

    # 3. All words appear anywhere (fallback)
    word_hits = [
        item for item in candidates
        if all(w in item[key].lower() for w in q_words)
    ]
    if word_hits:
        return min(word_hits, key=lambda x: abs(len(x[key]) - len(q)))

    # 4. Best similarity score (GPU: skip prose; require score strictly above floor)
    if not allow_similarity_fallback or not candidates:
        return None
    best = max(candidates, key=lambda x: similarity(q, x[key].lower()))
    score = similarity(q, best[key].lower())
    if min_similarity is not None and score <= min_similarity:
        return None
    return best


def parse_watts(w_str):
    """Parse '170W' -> 170"""
    try:
        return float(w_str.replace("W", "").replace("w", "").strip())
    except Exception:
        return 0.0


# ──────────────────────────────────────────────
# Component lookup helpers
# ──────────────────────────────────────────────

def lookup_cpu(query, cpu_list):
    match = fuzzy_match(query, cpu_list, "Series")
    if match:
        return match["Series"], parse_watts(match["Wattage"])
    return None, 0.0


def lookup_gpu(query, gpu_list):
    match = fuzzy_match(
        query,
        gpu_list,
        "GPU",
        min_similarity=GPU_FUZZY_MIN_SIMILARITY,
        allow_similarity_fallback=allow_gpu_stage4_similarity(query),
    )
    if match:
        return match["GPU"], parse_watts(match["Wattage"])
    return None, 0.0


def lookup_mb(mb_str):
    key = mb_str.lower().strip()
    if key in MB_WATTS:
        return MB_WATTS[key]
    # Fuzzy
    best_k = min(MB_WATTS.keys(), key=lambda k: -similarity(key, k))
    return MB_WATTS[best_k]


def lookup_ram(ram_str):
    key = ram_str.lower().strip()
    if key in RAM_WATTS:
        return RAM_WATTS[key]
    # Partial match
    for k, v in RAM_WATTS.items():
        if k in key or key in k:
            return v
    return 0.0


def lookup_ssd(ssd_str):
    key = ssd_str.lower().replace(" ", "").strip()
    for k, v in SSD_WATTS.items():
        if k.replace("-", "").replace(" ", "") in key or key in k.replace("-", "").replace(" ", ""):
            return v
    return 10.0  # default


def lookup_hdd(hdd_str):
    key = hdd_str.lower().replace(",", "").replace(" ", "")
    for k, v in HDD_WATTS.items():
        if k.replace(",", "").replace(" ", "") in key:
            return v
    return 20.0  # default 7200RPM


def lookup_optical(optical_str):
    key = optical_str.lower().strip()
    for k, v in OPTICAL_WATTS.items():
        if k in key or key in k:
            return v
    return 20.0


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
    if floor_applied:
        return (
            f"System draw {total_watts}W; after x1.2 headroom ~{headroom_watts}W, "
            f"still below the 550W catalog floor. Main recommendation is 550W as the "
            f"starting purchase tier (modular Gold availability)—not because the build "
            f"needs ~550W continuous, and not because 550W equals the 20% margin alone. "
            f"Users may pick a lower-wattage PSU on their own; the shop link stays at 550W."
        )
    return (
        f"System draw {total_watts}W; after x1.2 headroom ~{headroom_watts}W, "
        f"rounded up to the next catalog tier {recommended}W. "
        f"Main recommendation and first shop link must both be {recommended}W."
    )


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: calculate_psu.py '<json_spec>'"}))
        sys.exit(1)

    try:
        spec = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON spec: {e}"}))
        sys.exit(1)

    result = {
        "components": [],
        "total_watts": 0.0,
        "headroom_watts": 0.0,
        "recommended_psu_watts": 0,
        "catalog_floor_applied": False,
        "optional_higher_tier_watts": None,
        "recommendation_note": "",
        "shop_url": "",
        "warnings": [],
    }
    total = 0.0

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
            name, watts = lookup_gpu(gpu_raw, gpu_list)
            qty = int(spec.get("gpu_count", 1))
            if name:
                total += watts * qty
                result["components"].append({
                    "type": "GPU", "name": name, "watts": watts,
                    "count": qty, "subtotal": watts * qty
                })
            else:
                result["warnings"].append(
                    f"GPU '{gpu_raw}' not found or low-confidence match ignored; "
                    f"GPU wattage not included."
                )

    # ── Motherboard ──
    mb_raw = spec.get("mb")
    mb_defaulted = not (mb_raw is not None and str(mb_raw).strip())
    mb = "ATX" if mb_defaulted else str(mb_raw).strip()
    mb_watts = lookup_mb(mb)
    total += mb_watts
    mb_name = f"{mb} (default)" if mb_defaulted else mb
    result["components"].append({"type": "Motherboard", "name": mb_name, "watts": mb_watts})

    # ── RAM ──
    if spec.get("ram"):
        ram_watts = lookup_ram(spec["ram"])
        qty = int(spec.get("ram_count", 1))
        total += ram_watts * qty
        result["components"].append({
            "type": "RAM", "name": spec["ram"], "watts": ram_watts,
            "count": qty, "subtotal": ram_watts * qty
        })

    # ── SSD ──
    if spec.get("ssd"):
        ssd_watts = lookup_ssd(spec["ssd"])
        qty = int(spec.get("ssd_count", 1))
        total += ssd_watts * qty
        result["components"].append({
            "type": "SSD", "name": spec["ssd"], "watts": ssd_watts,
            "count": qty, "subtotal": ssd_watts * qty
        })

    # ── HDD ──
    if spec.get("hdd"):
        hdd_watts = lookup_hdd(spec["hdd"])
        qty = int(spec.get("hdd_count", 1))
        total += hdd_watts * qty
        result["components"].append({
            "type": "HDD", "name": spec["hdd"], "watts": hdd_watts,
            "count": qty, "subtotal": hdd_watts * qty
        })

    # ── Optical ──
    if spec.get("optical"):
        opt_watts = lookup_optical(spec["optical"])
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
    result["shop_url"] = (
        f"https://www.newegg.com/p/pl?d={recommended}W+PSU+modular+gold"
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
