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
calculates total wattage via the Newegg API + fixed tables.

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

### Grouping strategy

- **Round A** (core): CPU (if unknown) + GPU (if unknown)
- **Round B** (peripherals): RAM + storage (if unknown)
- If only 1 or 2 things are missing, combine them all into 1 call.
- If everything is already known, skip directly to Phase 2.

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
| ATX (default) | `mb` | `"ATX"` |
| 16GB DDR5 × 2 | `ram` + `ram_count` | `"16GB DDR5"`, `2` |
| SSD 1TB+ | `ssd` | `"1TB+"` |
| 2 × SSD 1TB+ | `ssd` + `ssd_count` | `"1TB+"`, `2` |
| HDD 7200RPM | `hdd` | `"7200RPM 3.5\""` |

**Example:**
```bash
python3 /path/to/scripts/calculate_psu.py \
  '{"cpu":"Ryzen 7 9800X3D","gpu":"RTX 5080","mb":"ATX","ram":"16GB DDR5","ram_count":2,"ssd":"1TB+"}'
```

---

## Phase 3 — Present results

The script outputs JSON with `total_watts` and `recommended_psu_watts`.

Show the user:

1. **Component breakdown table** — type, name, watts, count × subtotal
2. **Total system draw** — `total_watts`
3. **Recommended PSU** — `recommended_psu_watts` (already includes 20% safety buffer)
4. **PSU tier note**:
   - ≤650W → 650W PSU, Gold certification OK
   - 651–850W → 850W PSU, Gold minimum
   - 851–1000W → 1000W PSU, Platinum recommended
   - 1001W+ → 1200W PSU, Platinum/Titanium
5. **PCIe connector note** — for RTX 5000 series: must have PCIe 5.0 16-pin (600W native)
6. **Newegg shop link**: `https://www.newegg.com/p/pl?d=<WATTS>W+PSU+modular+gold`

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
