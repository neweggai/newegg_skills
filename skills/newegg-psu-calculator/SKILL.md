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
- "我有 Ryzen 7 9800X3D 和 RTX 5080" → CPU ✓ GPU ✓, only ask RAM + storage
- "我在考虑 RTX 4090，其他还没想好" → GPU ✓, ask CPU + RAM + storage
- "完全不知道配什么电源" → ask everything
- "i9-14900K + 64GB DDR5 + 2块 SSD" → CPU ✓ RAM ✓ SSD ✓, only ask GPU

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
- "你打算用哪颗 CPU？" (general)
- "CPU 还没确定，选一个吧：" (when user said they haven't decided)
- "CPU 用什么？" (casual, when user is already in spec-listing mode)
- "除了 [已知配件]，CPU 准备选哪颗？" (when some components are known)

**GPU question variants**:
- "独显用哪张？"
- "显卡选好了吗？选一下："
- "GPU 这边怎么配？"
- "搭配 [已知CPU]，显卡打算用哪张？"

**RAM question variants**:
- "内存怎么配？"
- "内存用多少？"
- "RAM 容量和代数？"

**Storage question variants**:
- "硬盘怎么配？"
- "存储方案？"
- "SSD 还是 SSD + 机械盘？"

---

## Component option menus (reference — use as needed)

### CPU options

**AMD Ryzen:**
```
- label: "Ryzen 5 9600X"      description: "6核 65W，性价比之选"
- label: "Ryzen 7 9700X"      description: "8核 65W，低功耗高性能"
- label: "Ryzen 7 9800X3D"    description: "8核 120W，3D Cache 游戏神机"
- label: "Ryzen 9 9950X"      description: "16核 170W，生产力旗舰"
- label: "其他 AMD 型号"        description: "9900X / 9950X3D / Threadripper 等"
```

**Intel Core:**
```
- label: "Core Ultra 5 235"    description: "10核 65W，入门主流"
- label: "Core Ultra 7 265K"   description: "20核 125W，高性能"
- label: "Core Ultra 9 285K"   description: "24核 125W，旗舰"
- label: "其他 Intel 型号"      description: "i9-14900K、i7-13700K 等"
```

If brand is unknown, merge into one list:
```
- label: "AMD Ryzen 7 9800X3D" description: "8核 120W"
- label: "AMD Ryzen 9 9950X"   description: "16核 170W"
- label: "Intel Core Ultra 7 265K" description: "20核 125W"
- label: "Intel Core Ultra 9 285K" description: "24核 125W"
- label: "其他 AMD 型号"
- label: "其他 Intel 型号"
```

Additional AMD options (for "其他"):
```
Ryzen 9 9950X3D (170W) / Ryzen 9 9900X (120W) / Ryzen 7 9850X3D (120W)
Threadripper PRO 9965WX / 9995WX / 9985WX (all 350W)
```

Additional Intel options (for "其他"):
```
Core Ultra 5 245K (125W) / Core Ultra 7 270K Plus (125W)
Core i9-14900K (125W) / Core i7-14700K (125W) / Core i5-14600K (125W)
```

---

### GPU options

**NVIDIA — show generation first if brand unknown; skip if already known:**
```
Generation picker:
- label: "RTX 50 系列（最新）"   description: "5060 Ti / 5070 / 5080 / 5090"
- label: "RTX 40 系列"          description: "4060 / 4070 / 4080 / 4090"
- label: "RTX 30 系列"          description: "3060 / 3070 / 3080 / 3090"
- label: "更旧 / GTX 系列"       description: "RTX 20 / GTX 16 / GTX 10"
```

**RTX 50 系列:**
```
- label: "RTX 5060 Ti"   description: "180W"
- label: "RTX 5070"      description: "250W"
- label: "RTX 5070 Ti"   description: "300W"
- label: "RTX 5080"      description: "360W"
- label: "RTX 5090"      description: "600W，终极旗舰"
- label: "其他 RTX 50"   description: "5060 145W / 5050 130W"
```

**RTX 40 系列:**
```
- label: "RTX 4060 / 4060 Ti"    description: "120W / 165W"
- label: "RTX 4070 / 4070 Super" description: "250W / 285W"
- label: "RTX 4070 Ti / 4080"    description: "300W / 340W"
- label: "RTX 4090"              description: "480W，旗舰"
- label: "其他 RTX 40"           description: "4080 SUPER 350W 等"
```

**RTX 30 系列:**
```
- label: "RTX 3060 / 3060 Ti"  description: "170W / 240W"
- label: "RTX 3070 / 3070 Ti"  description: "280W / 320W"
- label: "RTX 3080 / 3080 Ti"  description: "390W / 400W"
- label: "RTX 3090 / 3090 Ti"  description: "420W / 480W"
```

**AMD Radeon:**
```
- label: "RX 9070 / 9070 XT"    description: "220W / 340W，最新旗舰"
- label: "RX 7800 XT / 7700 XT" description: "288W / 245W，高性价比"
- label: "RX 7900 XTX / 7900 XT" description: "370W / 335W，旗舰"
- label: "RX 7600 / 9060 XT"    description: "185W / 182W，入门"
- label: "其他 AMD 显卡"         description: "RX 6900 XT / 6800 XT 等"
```

**No discrete GPU:**
```
- label: "不装独显"  description: "使用 CPU 核显"
- label: "还没决定" description: "先算其他配件"
```

---

### RAM options
```
- label: "8GB DDR5 × 2"    description: "双通道 16GB DDR5"
- label: "16GB DDR5 × 2"   description: "双通道 32GB DDR5（主流）"
- label: "32GB DDR5 × 2"   description: "双通道 64GB DDR5（高端）"
- label: "16GB DDR4 × 2"   description: "双通道 32GB DDR4"
- label: "其他配置"         description: "自定义容量或更多根数"
```

### Storage options
```
- label: "1 块 SSD（1TB+）"          description: "仅固态，11W"
- label: "2 块 SSD（1TB+ 各）"       description: "双固态，22W"
- label: "SSD + 机械 HDD（7200RPM）" description: "固态系统盘 + 机械存储"
- label: "其他"                       description: "自定义"
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
