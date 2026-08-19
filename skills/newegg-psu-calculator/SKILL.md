---
name: newegg-psu-calculator
description: >-
  Calculate the recommended PSU wattage for a PC build using Newegg's CPU/GPU
  wattage APIs plus fixed power tables for other components.
  Use this skill whenever users ask: "what PSU do I need?", "how many watts
  for my build?", "is my power supply enough?", "calculate power for my PC",
  or describe PC components (CPU + GPU + RAM + storage) and want to know what
  power supply to buy. Trigger even if the user hasn't explicitly mentioned PSU —
  wattage is the natural next question once someone lists their components.
---

# Newegg PSU Wattage Calculator

Intelligently collects component information through **adaptive menus**, then
calculates total wattage via live Newegg CPU/GPU wattage tables + fixed tables.

`scripts/calculate_psu.py` fetches the CPU and GPU wattage tables from the
`website-www-tool` endpoint (`apis.newegg.com/ex-mcp/...`, stateless JSON-RPC, no auth)
and sends `x-skill: newegg-psu-calculator` on every request. Nothing to install or
register; if a fetch fails the script degrades to a warning in `warnings[]` rather than
guessing a wattage.

**Core principle**: Be smart about what to ask. If the user already mentioned
components, skip those questions. Combine remaining unknowns into as few
`AskUserQuestion` calls as possible. Vary question wording based on context.

---

## Phase 0 — Parse the user's message first

Before asking anything, extract whatever components the user has already mentioned:

- CPU model or brand → mark as known
- GPU model or brand → mark as known
- RAM size/type → mark as known
- Storage config → mark as known
- Any other component mention → note it

Then proceed to collect only the **missing** information.

**Examples of smart extraction:**
- "I have a Ryzen 7 9800X3D and RTX 5080" → CPU ✓ GPU ✓, only ask RAM + storage
- "I'm thinking about an RTX 4090, haven't decided on the rest" → GPU ✓, ask CPU + RAM + storage
- "No idea what PSU I need" → ask everything
- "i9-14900K + 64GB DDR5 + 2 SSDs" → CPU ✓ RAM ✓ SSD ✓, only ask GPU

---

## Phase 1 — Collect unknowns via AskUserQuestion

Group missing components into **at most 2 AskUserQuestion calls**.
This ≤2-round limit applies **only to collecting parts** (Phase 1). It does **not**
forbid a Phase 3 optional follow-up (e.g. asking whether the user wants a higher-wattage link).

### Grouping strategy

- **Round A** (core): CPU (if unknown) + GPU (if unknown) — **must be one call**.
  Never split Round A into separate CPU-only then GPU-only turns when both are unknown.
- **Round B** (peripherals): RAM + storage (if unknown)
- If only 1 or 2 things are missing, combine them all into 1 call.
- If everything is already known, skip directly to Phase 2.
- **Threadripper / HEDT** (e.g. Threadripper, Threadripper PRO): if motherboard form
  factor is unknown, ask for it in the same round when possible; if still unknown,
  use `SSI CEB` or `SSI EEB` (150W), **not** silent consumer ATX. Menu "Other" Threadripper
  labels are model examples only — not a motherboard special-case by themselves.

### Adaptive question wording

Vary the question text to match context — do NOT use the same fixed wording every time.

**CPU question variants** (pick the most fitting):
- "Which CPU are you planning to use?" (general)
- "You haven't decided on a CPU yet — pick one:" (when user said they haven't decided)
- "What CPU?" (casual, when user is already in spec-listing mode)
- "Besides [known components], which CPU are you going with?" (when some components are known)

**GPU question variants**:
- "Which discrete GPU are you using?"
- "Have you picked a GPU? Choose one:"
- "What's your GPU?"
- "Paired with [known CPU], which GPU are you planning?"

**RAM question variants**:
- "How are you configuring your RAM?"
- "How much RAM?"
- "RAM capacity and generation?"

**Storage question variants**:
- "What's your storage setup?"
- "Storage configuration?"
- "SSD only, or SSD + HDD?"

---

## Component option menus (reference — use as needed)

### CPU options

**AMD Ryzen:**
```
- label: "Ryzen 5 9600X"      description: "6-core 65W, great value"
- label: "Ryzen 7 9700X"      description: "8-core 65W, low power high performance"
- label: "Ryzen 7 9800X3D"    description: "8-core 120W, 3D Cache gaming champion"
- label: "Ryzen 9 9950X"      description: "16-core 170W, productivity flagship"
- label: "Other AMD model"     description: "9900X / 9950X3D / Threadripper, etc."
```

**Intel Core:**
```
- label: "Core Ultra 5 235"    description: "10-core 65W, mainstream entry"
- label: "Core Ultra 7 265K"   description: "20-core 125W, high performance"
- label: "Core Ultra 9 285K"   description: "24-core 125W, flagship"
- label: "Other Intel model"   description: "i9-14900K, i7-13700K, etc."
```

If brand is unknown, merge into one list:
```
- label: "AMD Ryzen 7 9800X3D"     description: "8-core 120W"
- label: "AMD Ryzen 9 9950X"       description: "16-core 170W"
- label: "Intel Core Ultra 7 265K" description: "20-core 125W"
- label: "Intel Core Ultra 9 285K" description: "24-core 125W"
- label: "Other AMD model"
- label: "Other Intel model"
```

Additional AMD options (for "Other"):
```
Ryzen 9 9950X3D (170W) / Ryzen 9 9900X (120W) / Ryzen 7 9850X3D (120W)
Threadripper PRO 9965WX / 9995WX / 9985WX (all 350W)
```

Additional Intel options (for "Other"):
```
Core Ultra 5 245K (125W) / Core Ultra 7 270K Plus (125W)
Core i9-14900K (125W) / Core i7-14700K (125W) / Core i5-14600K (125W)
```

---

### GPU options

**NVIDIA — show generation first if brand unknown; skip if already known:**
```
Generation picker:
- label: "RTX 50 Series (Latest)"  description: "5060 Ti / 5070 / 5080 / 5090"
- label: "RTX 40 Series"           description: "4060 / 4070 / 4080 / 4090"
- label: "RTX 30 Series"           description: "3060 / 3070 / 3080 / 3090"
- label: "Older / GTX Series"      description: "RTX 20 / GTX 16 / GTX 10"
```

**RTX 50 Series:**
```
- label: "RTX 5060 Ti"    description: "180W"
- label: "RTX 5070"       description: "250W"
- label: "RTX 5070 Ti"    description: "300W"
- label: "RTX 5080"       description: "360W"
- label: "RTX 5090"       description: "600W, ultimate flagship"
- label: "Other RTX 50"   description: "5060 145W / 5050 130W"
```

**RTX 40 Series:**
```
- label: "RTX 4060 / 4060 Ti"    description: "120W / 165W"
- label: "RTX 4070 / 4070 Super" description: "250W / 285W"
- label: "RTX 4070 Ti / 4080"    description: "300W / 340W"
- label: "RTX 4090"              description: "480W, flagship"
- label: "Other RTX 40"          description: "4080 SUPER 350W, etc."
```

**RTX 30 Series:**
```
- label: "RTX 3060 / 3060 Ti"  description: "170W / 240W"
- label: "RTX 3070 / 3070 Ti"  description: "280W / 320W"
- label: "RTX 3080 / 3080 Ti"  description: "390W / 400W"
- label: "RTX 3090 / 3090 Ti"  description: "420W / 480W"
```

**AMD Radeon:**
```
- label: "RX 9070 / 9070 XT"     description: "220W / 340W, latest flagship"
- label: "RX 7800 XT / 7700 XT"  description: "288W / 245W, great value"
- label: "RX 7900 XTX / 7900 XT" description: "370W / 335W, flagship"
- label: "RX 7600 / 9060 XT"     description: "185W / 182W, entry level"
- label: "Other AMD GPU"          description: "RX 6900 XT / 6800 XT, etc."
```

**No discrete GPU:**
```
- label: "No discrete GPU"  description: "Using CPU integrated graphics"
- label: "Not decided yet"  description: "Calculate other components first"
```

---

### RAM options
```
- label: "8GB DDR5 × 2"    description: "Dual-channel 16GB DDR5"
- label: "16GB DDR5 × 2"   description: "Dual-channel 32GB DDR5 (mainstream)"
- label: "32GB DDR5 × 2"   description: "Dual-channel 64GB DDR5 (high-end)"
- label: "16GB DDR4 × 2"   description: "Dual-channel 32GB DDR4"
- label: "Other config"     description: "Custom capacity or more sticks"
```

### Storage options
```
- label: "1 SSD (1TB+)"              description: "SSD only, 11W"
- label: "2 SSDs (1TB+ each)"        description: "Dual SSD, 22W"
- label: "SSD + HDD (7200RPM)"       description: "SSD for OS + HDD for storage"
- label: "Other"                      description: "Custom configuration"
```

---

## Phase 2 — Build the JSON spec and run the script

Map all selections to the JSON spec format and run:

```bash
python3 <skill_base_dir>/scripts/calculate_psu.py '<json_spec>'
```

**Mapping guide:**

| Selection | JSON field | Value |
|-----------|------------|-------|
| Ryzen 7 9800X3D | `cpu` | `"Ryzen 7 9800X3D"` |
| RTX 5080 | `gpu` | `"RTX 5080"` |
| 2 GPUs | `gpu_count` | `2` |
| ATX (default) | `mb` | `"ATX"` (if omitted, script defaults ATX — **label as default** in Phase 3) |
| Threadripper, mb unknown | `mb` | `"SSI CEB"` or `"SSI EEB"` (prefer asking first) |
| 16GB DDR5 × 2 | `ram` + `ram_count` | `"16GB DDR5"`, `2` |
| SSD 1TB+ | `ssd` | `"1TB+"` |
| 2 × SSD 1TB+ | `ssd` + `ssd_count` | `"1TB+"`, `2` |
| HDD 7200RPM | `hdd` | `"7200RPM 3.5\""` |
| No discrete GPU / iGPU / 无独显 / 核显 / none / Not decided yet | `gpu` | **Omit `gpu`**, or `""`, or pass the phrase (script maps known phrases → 0W). Do **not** invent a discrete model. |
| User said "no GPU" in free text not in the script list | — | Prefer omit `gpu` / `""` / a known phrase rather than a prose string that may only warn |

**Example:**
```bash
python3 /path/to/scripts/calculate_psu.py \
  '{"cpu":"Ryzen 7 9800X3D","gpu":"RTX 5080","mb":"ATX","ram":"16GB DDR5","ram_count":2,"ssd":"1TB+"}'
```

---

## Phase 3 — Present results

Script JSON fields (use these; do not invent numbers):

| Field | Meaning |
|-------|---------|
| `total_watts` | Component sum |
| `headroom_watts` | `total_watts × 1.2` |
| `recommended_psu_watts` | **Sole main recommendation** (catalog tier) |
| `catalog_floor_applied` | `true` when headroom &lt; 550 but rec is 550 |
| `optional_higher_tier_watts` | Next tier above main (for verbal mention / later link only) |
| `recommendation_note` | Wording guidance — follow it |
| `shop_url` | First (and only) link in the first reply; wattage == main rec |

### Hard rules — ticket #14 (main rec / wording / link must align)

1. **Main recommendation** = `recommended_psu_watts` only. Never treat a higher tier as the primary pick.
2. **First shop link** = `shop_url` (or build URL with the **same** wattage). Forbidden: main says 550W but link is `d=650W`, or main says 750W while copy pushes 650W as the buy target.
3. You may **verbally** mention `optional_higher_tier_watts` for upgrade headroom (one short sentence). That mention is **not** a second recommendation and must not get a link yet.
4. **End of first reply:** ask if they want a higher-wattage shop link. Give a second link **only after** the user agrees.
5. Do **not** dump multiple conflicting wattages + multiple links in the first reply.

### Hard rules — ticket #15 (550 floor wording)

1. Keep **550W** as the default minimum purchase tier (do not change script floor to 450/500).
2. When `catalog_floor_applied` is `true` (typical iGPU / low-draw builds ~150–210W):
   - **Do not** say the 550W pick “已含 20% 余量” / “already includes 20% safety margin” as if 550 ≈ draw×1.2.
   - **Do** say: after ×1.2 the need is still well below 550; **550W is the starting catalog tier** we recommend for modular Gold availability/quality.
   - Optional: user may choose a lower-wattage PSU themselves; **our shop link stays at 550W**.
3. When `catalog_floor_applied` is `false`, you may say the tier includes ~20% headroom then rounds up to the next catalog tier — still keep main rec and first link identical.
4. Prefer `recommendation_note` from the script when unsure.

### Presentation order

1. **Component breakdown table** — type, name, watts, count × subtotal  
   - If motherboard was not specified by the user, label it as **ATX (default)** (or whatever default the script used).
2. **Total system draw** — `total_watts` (optionally show `headroom_watts`)
3. **Recommended PSU** — `recommended_psu_watts` only, with #15-compliant wording
4. **PSU tiers** (must match `PSU_TIERS` in `calculate_psu.py`): 550 · 650 · 750 · 850 · 1000 · 1200 · 1600  
   - Guidance: 550–750 Gold modular OK; 850+ prefer Gold minimum; 1000+ Platinum when budget allows.
5. **PCIe connector note** — for RTX 5000 series: must have PCIe 5.0 16-pin (600W native)
6. **First Newegg shop link** — `shop_url` (wattage == main recommendation)
7. Optional one-line higher-tier mention + **ask** before any second link
8. **Existing PSU comparison:** only if the user clearly stated an existing PSU **in this turn**. Never invent “you already have a 750W PSU.”

---

## Fallback wattage tables (for manual calculation if script unavailable)

### Motherboard
ATX 70W · E-ATX 100W · Micro ATX 60W · Mini-ITX 30W · Thin Mini-ITX 20W · SSI CEB/EEB 150W · XL AT 130W

### RAM (per stick)
192GB DDR5 57.6W · 128GB DDR5 38.4W · 64GB DDR5 19.2W · 32GB DDR5 9.6W · 16GB DDR5 4.8W · 8GB DDR5 2.4W · 4GB DDR5 1.2W
192GB DDR4 72W · 64GB DDR4 24W · 32GB DDR4 12W · 16GB DDR4 6W · 8GB DDR4 3W · 4GB DDR4 1.5W

### SSD · HDD · Optical
SSD under 512GB 10W · SSD 512GB–1TB+ 11W
HDD 5400RPM 15W · 7200RPM 20W · 10K RPM 30W · 15K RPM 40W
Optical: Blu-Ray/DVD-RW 30W · COMBO 24W · DVD-ROM 20W · CD-RW 16W · CD-ROM 15W
