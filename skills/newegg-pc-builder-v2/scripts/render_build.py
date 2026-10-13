#!/usr/bin/env python3
"""
Deterministic final-output renderer for the newegg-pc-builder-v2 skill.

Why this exists: validate_output.py checks a drafted response AFTER the
model writes it — which only works if the model actually chooses to run
the check. On non-Claude platforms that has failed repeatedly (leaked
narration, missing cart link, missing disclaimer, mixed-language card
content), because the check itself is just another instruction the model
can skip.

This script removes the model's discretion over the failure-prone part
instead of trying to police it after the fact: it takes the structured
component data and produces the ENTIRE core recommendation block —
heading, table, combo note, badges, cart link, disclaimer — as plain
text, byte-for-byte. The model's job shrinks to: call this script, then
output its result verbatim as the core block. There is no drafting step
for that block, so there is nothing to leak into it and nothing to
"forget" to include, regardless of how faithfully the calling model
follows written instructions.

This still cannot force the model to (a) actually call this script
instead of hand-writing the block, or (b) refrain from typing its own
preamble before pasting the result. Those two risks are no longer about
content correctness — they're about tool-call compliance, which no local
script can guarantee from outside the model's own decision loop. The only
fully robust fix for that residual risk is a server-side/platform-side
post-processing hook that runs independent of the model's cooperation
(see SKILL.md's Cross-Platform Portability section).

Usage:
  python3 scripts/render_build.py < build.json
  python3 scripts/render_build.py --file build.json

Input JSON shape:
{
  "budget": 1500,                     // number, no currency symbol
  "components": [
    {
      "category": "CPU",              // display label, left column
      "name": "AMD Ryzen 7 9800X3D",  // English product name
      "item_number": "19-113-877",    // raw Newegg item/SKU number
      "unit_price": 479.00,
      "rebate": 0.0,                  // instant rebate, defaults 0
      "combo_saving": 20.0,           // this item's contribution to combo
                                      //   savings, defaults 0
      "owned": false                  // true = user already owns this;
                                      //   excluded from total + cart
    },
    ...
  ],
  "compatibility_ok": true,
  "power_ok": true,
  "combo_note": "CPU + storage bundle save $25.00 total",  // omit/empty
                                                             // to hide line
  "utm_source": "claude"              // per environment_detection.md
}

Output: the exact Markdown block to use as the core recommendation
message — nothing before it, nothing rewritten inside it.
"""

import sys
import json
import argparse
import re


def build_item_url(item_number, utm_source):
    """Mirror reference/product_link_rules.md exactly."""
    has_letters = bool(re.search(r"[A-Za-z]", item_number))
    if has_letters:
        # Marketplace-format SKU — used as-is.
        path_id = item_number
    else:
        digits = item_number.replace("-", "")
        path_id = f"N82E168{digits}"
    return (
        f"https://www.newegg.com/p/{path_id}?Item={path_id}"
        f"&utm_source={utm_source}&utm_medium=ai_skill"
        f"&utm_campaign=pc-builder&utm_content=newegg-pc-builder"
    )


def build_cart_url(item_numbers):
    parts = [f"{num}.PCDIY4|1" for num in item_numbers]
    item_list = "%2C".join(parts)
    return (
        f"https://secure.newegg.com/api/shop/add?Submit=Add"
        f"&ItemList={item_list}"
    )


def render(data):
    utm_source = data.get("utm_source", "claude")
    components = data["components"]
    budget = data.get("budget")

    lines_priced = []      # components counted toward total/cart
    owned_lines = []        # components marked owned — shown, not priced
    total = 0.0
    pre_combo_total = 0.0
    combo_savings_total = 0.0
    cart_item_numbers = []

    for c in components:
        category = c["category"]
        name = c["name"]
        item_number = c["item_number"]
        owned = c.get("owned", False)

        if owned:
            owned_lines.append((category, name))
            continue

        unit_price = float(c["unit_price"])
        rebate = float(c.get("rebate", 0.0))
        combo_saving = float(c.get("combo_saving", 0.0))
        line_price = unit_price - rebate

        pre_combo_total += line_price
        combo_savings_total += combo_saving
        total += line_price
        cart_item_numbers.append(item_number)

        url = build_item_url(item_number, utm_source)
        lines_priced.append(
            (category, f"[{name}]({url})", f"${line_price:,.2f}")
        )

    total -= combo_savings_total

    # --- Heading -------------------------------------------------------
    if budget is not None:
        if total <= budget * 1.05:
            status = "within budget" if total <= budget else (
                f"~{round((total / budget - 1) * 100)}% over budget"
            )
        else:
            status = f"~{round((total / budget - 1) * 100)}% over budget"
        heading_suffix = f" ({status})"
    else:
        heading_suffix = ""

    out = []
    if combo_savings_total > 0:
        out.append(
            f"## Recommended build — ${total:,.2f} "
            f"~~${pre_combo_total:,.2f}~~{heading_suffix}"
        )
    else:
        out.append(f"## Recommended build — ${total:,.2f}{heading_suffix}")
    out.append("")

    # --- Table -----------------------------------------------------------
    out.append("| Part | Model | Price |")
    out.append("|------|-------|-------|")
    for category, model_link, price in lines_priced:
        out.append(f"| {category} | {model_link} | {price} |")
    for category, name in owned_lines:
        out.append(f"| {category} | {name} (your existing part) | owned |")
    out.append("")

    # --- Combo note --------------------------------------------------
    combo_note = data.get("combo_note", "").strip()
    if combo_note:
        out.append(f"**Combo savings (applied automatically):** {combo_note}")
        out.append("")

    # --- Badges ------------------------------------------------------
    badges = []
    if data.get("compatibility_ok"):
        badges.append("✅ Compatibility verified")
    if data.get("power_ok"):
        badges.append("✅ Power headroom: good")
    if badges:
        out.append(" · ".join(badges))
        out.append("")

    # --- Add to cart (always present, always here) --------------------
    if cart_item_numbers:
        cart_url = build_cart_url(cart_item_numbers)
        out.append(f"🛒 [Add to cart]({cart_url})")
        out.append("")

    # --- Disclaimer (always present, always here, always English) -----
    out.append(
        "Prices, promo codes, and stock status shown are subject to "
        "change — please confirm final pricing at checkout on Newegg.com."
    )

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="Read build JSON from this file "
                                        "instead of stdin.")
    args = parser.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    print(render(data))


if __name__ == "__main__":
    main()
