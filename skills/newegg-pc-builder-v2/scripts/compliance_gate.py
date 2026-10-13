#!/usr/bin/env python3
"""
Compliance gate for the newegg-pc-builder-v2 skill (supersedes the older
validate_output.py as the mandatory pre-send/pre-render check).

WHY THIS EXISTS
----------------
validate_output.py checked four things mechanically (narration leak, cart
link, card language, disclaimer) but the rest of this skill's hard
requirements (Step 5a-5d verification, "never borrow another skill's
files," the Step 0.0 fresh language check, render_build.py actually being
used, a generated file actually being surfaced to the user, ...) still
lived only as prose the model was supposed to "remember to do." That
degrades on platforms that don't weight written instructions the way
Claude does (observed on AngX: missing cart links, missing disclaimer,
and separately, chat text with a plain-text link/file that was never
actually surfaced to the user because the delivery-tool call was skipped).

This script turns EVERY hard requirement in SKILL.md into either:
  (a) a mechanical check against the drafted text (regex-based), or
  (b) a mechanical check against a separately-supplied artifact this turn
      actually produced (e.g. --rendered-block-file, checked for verbatim
      inclusion — see H14 below), or
  (c) an explicit --evidence flag the agent must declare for THIS turn
      (an action that genuinely can't be verified any other way).
Undeclared/unsupplied = failure, not a pass. There is no fourth category
of "trust the model's self-report with nothing to check it against."

🚨 RUN THIS ON THE LITERAL TEXT YOU ARE ABOUT TO SEND — NOT A DRAFT
---------------------------------------------------------------------
This has been the exact, repeated failure mode in practice: the gate was
run against a correct draft (or against render_build.py's raw output),
and then the message actually sent was reassembled/rewritten afterward —
by hand, from memory of what the draft contained — and the cart
link/table got dropped or altered in that second, unchecked step. A gate
that approves draft A while draft B ships is not a gate. There is no way
for this script to detect that the text piped into it isn't what's
actually sent — that has to be a discipline the calling agent holds. The
practical rule: pipe in the exact string, character for character, that
you are about to output as your reply. If you touch that string again
after this script passes — reformatting, adding a sentence, "cleaning up"
the table — that is a new draft, and you must run the gate again on the
new final text before sending it.

HARD vs. SOFT, AND WHY THIS IS NOT A "SCORE THRESHOLD" GATE
-------------------------------------------------------------
Every rule below carries a weight (they sum to 100) purely for reporting
and audit purposes — see reference/compliance_rules.md for the full table
and the rationale for each weight. The weights do NOT trade off against
each other. A single failed HARD rule blocks the send, full stop, no
matter how high the resulting score is on paper. Do not read "score
92/100" as "good enough to send" if even one HARD rule is in the failure
list — that would silently reintroduce exactly the "partial credit hides
a critical miss" failure mode this script exists to prevent. Only the
SOFT rules are advisory: failing one is reported for visibility but never
blocks sending.

USAGE
-----
  python3 scripts/compliance_gate.py \
      --claude-env yes --format markdown \
      --rendered-block-file rendered_block.txt \
      --evidence '{"step0_language_checked": true, "step5a_compatibility": true,
                   "step5b_psu": true, "step5c_value_compare": true,
                   "step5d_stock": true, "no_borrowed_files": true}' \
      < draft.txt

  python3 scripts/compliance_gate.py --lightweight < draft.txt
      # single compatibility/price Q&A that never triggers Step 9 at all

Flags:
  --claude-env yes|no        required unless --lightweight (see Step 9)
  --format markdown|card     required unless --lightweight
  --markdown-fallback-reason required only if claude-env=yes AND format=markdown
  --rendered-block '<text>' | --rendered-block-file <path>
                              REQUIRED when --format markdown and not
                              --lightweight: the exact, unmodified stdout of
                              scripts/render_build.py for this turn. The
                              script checks that this text appears verbatim
                              (whitespace-normalized only) inside the final
                              draft — this is the mechanical fix for "the
                              model hand-rewrote the table instead of
                              pasting the rendered block," which is what
                              has actually dropped the cart link in
                              practice. Self-declaring "I used the render"
                              is no longer accepted for this rule.
  --produced-file            pass this if the turn wrote/generated a file the
                              user needs to open (not the normal path for this
                              skill's own card/Markdown output, but some
                              platforms — e.g. AngX — have been observed doing
                              this instead of inlining the block; if it
                              happens, the delivery step is mandatory, not
                              optional)
  --upgrade-question-seen    pass this if the MCP endpoint asked the
                              build-vs-upgrade meta-question this turn (see
                              SKILL.md "Scope: brand-new build only")
  --is-swap                  pass this if this turn is an add/remove/swap on
                              an already-presented config (triggers the Step 9
                              full-reprocess soft check)
  --skip-disclaimer          same meaning as before: lightweight single-item
                              Q&A that never triggers Step 9's full render
  --lightweight              shorthand for: this turn never reached Step 9 at
                              all (skips every Step 5/9/10-scoped rule, keeps
                              only the universal ones: narration leak,
                              language self-check, no-borrowed-files)
  --evidence '<json>' | --evidence-file <path>
                              JSON object of booleans for the remaining
                              non-mechanical hard rules (see
                              reference/compliance_rules.md). Any key not
                              present is treated as false.
  --file <path>               read drafted text from a file instead of stdin

Exit code 0 -> "ALL HARD CHECKS PASSED" (+ score) -> safe to send.
Exit code 1 -> "FAILED" (+ list of failed HARD rules) -> do not send.
Exit code 2 -> usage/input error (e.g. empty draft, bad --evidence JSON).
"""

import sys
import re
import json
import argparse


# =============================================================================
# Mechanical (text-based) check helpers — extended from validate_output.py
# =============================================================================

BANNED_NARRATION_PATTERNS = [
    r"utm_source\s*=",
    r"runtime environment",
    r"platform signal",
    r"no claude[- ]exclusive tool",
    r"claude[- ]exclusive tool",
    r"comboCompatibleAll",
    r"calculate_psu\.py",
    r"mcp_client\.py",
    r"render_build\.py",
    r"compliance_gate\.py",
    r"validate_output\.py",
    r"\bjson-rpc\b",
    r"the interface (originally|returned)",
    r"the (system|backend) (returned|gave)",
    r"all data (is|are) (ready|complete|gathered)",
    r"presenting the final plan directly",
    r"呈现最终方案",
    r"已齐全",
    r"可确定的平台",
    r"平台信号",
    r"无\s*claude\s*专属工具",
    r"内部逻辑",
    r"what happened behind this recommendation",
    r"延续.{0,8}(上一轮|上次|之前)",
    r"上一轮同样的情况",
    r"并非配置出错",
    r"没有虚标",
    r"数据快照",
    r"按实价呈现",
    r"我按实价",
    r"没有.{0,4}替换",
]

ADD_TO_CART_PATTERNS = [
    r"add to cart",
    r"secure\.newegg\.com/api/shop/add",
    r"openLink\(",
]

CARD_LINE_MARKERS = [
    r"^\s*\|",
    r"compatibility verified",
    r"power headroom",
    r"combo savings",
    r"promo code savings",
    r"recommended build",
    r"out of stock",
]

FOREIGN_SCRIPT_RE = re.compile(
    r"["
    r"\u4E00-\u9FFF"
    r"\u3040-\u30FF"
    r"\u3400-\u4DBF"
    r"\uAC00-\uD7A3"
    r"\u3000-\u303F"
    r"\uFF00-\uFFEF"
    r"\u0400-\u04FF"
    r"\u0600-\u06FF"
    r"]"
)

DISCLAIMER_REQUIRED_SUBSTRINGS = ["subject to change", "confirm final pricing"]

MARKDOWN_TABLE_HEADER_RE = re.compile(
    r"\|\s*part\s*\|\s*model\s*\|\s*price\s*\|", re.IGNORECASE
)
MARKDOWN_TABLE_SEP_RE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")
HTML_MARKUP_MARKERS = [r"<div", r"<table", r"<button", r"<span", r"onclick=\"openLink\("]
HEADING_OR_TABLE_RE = re.compile(r"^\s*(#{1,3}\s|\|)")

# reference/product_link_rules.md: every product/cart URL must carry a
# utm_source that isn't a leftover placeholder, and a cart link must not
# contain an obviously-unfilled item number.
PLACEHOLDER_TOKENS_RE = re.compile(
    r"(itemnumber|item_number|\{item|undefined|null|tbd|xxxx+)", re.IGNORECASE
)
NEWEGG_LINK_RE = re.compile(r"https://www\.newegg\.com/p/\S+", re.IGNORECASE)
CART_LINK_RE = re.compile(r"https://secure\.newegg\.com/api/shop/add\?\S+", re.IGNORECASE)
UTM_SOURCE_RE = re.compile(r"utm_source=([a-z_]+)", re.IGNORECASE)

TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
TABLE_SEP_CELL_RE = re.compile(r"^[\s\-:]+$")
ITEM_LIST_RE = re.compile(r"ItemList=([^&\s)\"']+)", re.IGNORECASE)


def _is_url_line(line):
    return "http://" in line or "https://" in line


def check_narration(text):
    failures = []
    for line in text.splitlines():
        if _is_url_line(line):
            continue
        lowered = line.lower()
        for pat in BANNED_NARRATION_PATTERNS:
            if re.search(pat, lowered, flags=re.IGNORECASE):
                failures.append(
                    f"Leaked internal-process narration matched {pat!r} on: {line.strip()!r}"
                )
    return failures


def check_preamble(text, fmt):
    if fmt == "card":
        return []
    lines = text.splitlines()
    preamble_lines = []
    for line in lines:
        if HEADING_OR_TABLE_RE.match(line):
            break
        if line.strip():
            preamble_lines.append(line.strip())
    if preamble_lines:
        return [
            "Text found BEFORE the build heading/table: "
            + " / ".join(preamble_lines)
            + ". Step 9 output must lead with the build itself."
        ]
    return []


def check_add_to_cart(text):
    for pat in ADD_TO_CART_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            return []
    return ["No Add to cart link/button found."]


def check_card_language(text):
    failures = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        is_card_line = any(
            re.search(m, stripped, flags=re.IGNORECASE) for m in CARD_LINE_MARKERS
        )
        if not is_card_line:
            continue
        hits = FOREIGN_SCRIPT_RE.findall(stripped)
        if hits:
            failures.append(f"Non-English content on a card/table line: {stripped!r}")
    return failures


def check_disclaimer(text, skip):
    if skip:
        return []
    lowered = text.lower()
    if all(s in lowered for s in DISCLAIMER_REQUIRED_SUBSTRINGS):
        return []
    return ["Disclaimer line not found (must contain 'subject to change' and "
            "'confirm final pricing')."]


def check_format_matches_environment(text, claude_env, fmt, fallback_reason):
    failures = []
    has_md_table = bool(MARKDOWN_TABLE_HEADER_RE.search(text)) or any(
        MARKDOWN_TABLE_SEP_RE.match(line) for line in text.splitlines()
    )
    has_html_markup = any(
        re.search(pat, text, flags=re.IGNORECASE) for pat in HTML_MARKUP_MARKERS
    )
    if claude_env and fmt == "markdown":
        if not fallback_reason or not fallback_reason.strip():
            failures.append(
                "claude-env=yes + format=markdown requires "
                "--markdown-fallback-reason stating the actual widget-call "
                "error. This combination without a reason means the Step 9 "
                "mandatory-card rule was skipped."
            )
    if not claude_env and fmt == "card":
        failures.append(
            "claude-env=no + format=card is never valid — a non-Claude "
            "environment cannot render visualize:show_widget output."
        )
    if fmt == "card":
        if not has_html_markup:
            failures.append(
                "format=card declared but no HTML markup found in the piped "
                "content — pipe in the actual widget_code, not chat prose."
            )
        if has_md_table:
            failures.append(
                "format=card declared but a Markdown pipe-table was found — "
                "looks like the Markdown template was pasted by mistake."
            )
    if fmt == "markdown" and has_html_markup and not has_md_table:
        failures.append(
            "format=markdown declared but the content looks like HTML card "
            "markup with no Markdown table found."
        )
    return failures


def check_links_well_formed(text, lightweight):
    if lightweight:
        return []
    failures = []
    product_links = NEWEGG_LINK_RE.findall(text)
    cart_links = CART_LINK_RE.findall(text)
    for link in product_links + cart_links:
        if PLACEHOLDER_TOKENS_RE.search(link):
            failures.append(f"Placeholder/unfilled token found in a URL: {link}")
    for link in product_links:
        if "utm_source=" not in link.lower():
            failures.append(f"Product link missing utm_source parameter: {link}")
        else:
            m = UTM_SOURCE_RE.search(link)
            if m and m.group(1).lower() in ("", "none", "todo"):
                failures.append(f"Product link has an empty/placeholder utm_source: {link}")
    return failures


def _parse_table_rows(text):
    """Return list of (cells) for every real data row of the fixed
    Part|Model|Price table — skips the header row and the '---' separator
    row. Tolerant of extra whitespace inside cells."""
    rows = []
    for line in text.splitlines():
        m = TABLE_ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if len(cells) < 3:
            continue
        if cells[0].lower() == "part" and cells[1].lower() == "model":
            continue  # header row
        if all(TABLE_SEP_CELL_RE.match(c) for c in cells):
            continue  # '|---|---|---|' separator row
        rows.append(cells)
    return rows


def check_cart_item_count(text, lightweight):
    """H17: the number of items in the Add-to-cart link's ItemList must
    equal the number of non-owned rows in the component table. Directly
    targets the reported failure where a cart link was regenerated/typed
    by hand and ended up with a different item count than the table it
    sits next to (or the reverse: a component was quietly dropped from
    the link during manual reassembly)."""
    if lightweight:
        return []
    rows = _parse_table_rows(text)
    if not rows:
        return []  # no table to compare against (e.g. card path uses HTML, not a Markdown table)

    def _is_owned_row(cells):
        price_cell = cells[2].strip().lower()
        model_cell = cells[1].strip().lower()
        return (price_cell == "owned"
                or "existing part" in model_cell
                or "already own" in model_cell)

    total_rows = len(rows)
    owned_rows = sum(1 for r in rows if _is_owned_row(r))
    expected_count = total_rows - owned_rows

    cart_links = CART_LINK_RE.findall(text)
    if not cart_links:
        return []  # missing link entirely is H3's job, not this rule's

    link = cart_links[0]
    m = ITEM_LIST_RE.search(link)
    if not m:
        return [f"Cart link found but its ItemList parameter could not be parsed: {link}"]
    segments = [s for s in re.split(r"%2[cC]|,", m.group(1)) if s.strip()]
    cart_count = len(segments)

    if cart_count != expected_count:
        return [
            f"Cart link lists {cart_count} item(s) but the table shows "
            f"{expected_count} non-owned component(s) ({total_rows} total rows, "
            f"{owned_rows} marked owned) — these must match exactly. "
            f"Link: {link}"
        ]
    return []


def _normalize_block(s):
    """Whitespace-normalize for verbatim comparison: strip trailing
    whitespace per line and surrounding blank lines, but never touch
    wording/content — this must not tolerate a reworded or reformatted
    block, only incidental whitespace differences from copy/paste."""
    lines = [ln.rstrip() for ln in s.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def check_rendered_block_verbatim(text, rendered_block, fmt, lightweight):
    """H14: on the Markdown path, the core block must be render_build.py's
    actual output, included verbatim — not a hand-rewritten table that
    merely resembles it. This is the direct fix for 'the gate approved a
    draft that used the render, but the message that was actually typed
    out afterward silently dropped the cart link.'"""
    if lightweight or fmt != "markdown":
        return []
    if rendered_block is None:
        return [
            "No --rendered-block/--rendered-block-file supplied. For the "
            "Markdown path this is required — self-declaring that "
            "render_build.py was used is no longer sufficient; supply its "
            "actual output so it can be verified verbatim."
        ]
    normalized_block = _normalize_block(rendered_block)
    normalized_text = _normalize_block(text)
    if not normalized_block.strip():
        return ["--rendered-block/--rendered-block-file was empty."]
    if normalized_block not in normalized_text:
        return [
            "The final draft does NOT contain render_build.py's output "
            "verbatim (whitespace-only normalization was applied — wording, "
            "rows, links, and the disclaimer must match exactly). This is "
            "exactly the failure mode where a table gets hand-rewritten or "
            "reassembled after the render step, silently dropping the cart "
            "link, a row, or the disclaimer. Paste the rendered block's "
            "output unchanged; put any additional rationale/notes outside it."
        ]
    return []


# =============================================================================
# Rule inventory: HARD (blocking) + SOFT (advisory, weighted only)
# =============================================================================
# Each rule: id, name, category, weight, applicable(ctx)->bool, check(ctx)->list[str]
# check() returns a list of failure strings; empty list = pass.

def build_rules():
    rules = []

    def add(rule_id, name, category, weight, applicable, check):
        rules.append(dict(id=rule_id, name=name, category=category,
                           weight=weight, applicable=applicable, check=check))

    always = lambda ctx: True
    not_lightweight = lambda ctx: not ctx["lightweight"]

    # ---- HARD, mechanical (text-based), weight sum adjusted below ----
    add("H1", "No leaked internal-process narration", "HARD", 5,
        always, lambda ctx: check_narration(ctx["text"]))

    add("H2", "No preamble before build heading/table", "HARD", 2,
        not_lightweight, lambda ctx: check_preamble(ctx["text"], ctx["fmt"]))

    add("H3", "Add to cart link/button present", "HARD", 7,
        not_lightweight, lambda ctx: check_add_to_cart(ctx["text"]))

    add("H4", "Card/table content is English-only", "HARD", 5,
        not_lightweight, lambda ctx: check_card_language(ctx["text"]))

    add("H5", "Disclaimer line present", "HARD", 7,
        lambda ctx: not ctx["lightweight"] and not ctx["skip_disclaimer"],
        lambda ctx: check_disclaimer(ctx["text"], ctx["skip_disclaimer"]))

    add("H6", "Declared env/format are consistent with each other and the content", "HARD", 7,
        not_lightweight,
        lambda ctx: check_format_matches_environment(
            ctx["text"], ctx["claude_env"], ctx["fmt"], ctx["markdown_fallback_reason"]))

    add("H7", "Product/cart links carry no placeholder tokens and a real utm_source", "HARD", 3,
        not_lightweight, lambda ctx: check_links_well_formed(ctx["text"], ctx["lightweight"]))

    add("H17", "Cart link item count matches non-owned component count in the table", "HARD", 6,
        not_lightweight, lambda ctx: check_cart_item_count(ctx["text"], ctx["lightweight"]))

    # ---- HARD, evidence-based (weight sum adjusted below) ----
    def evidence_check(key, message):
        def _check(ctx):
            if ctx["evidence"].get(key) is True:
                return []
            return [f"--evidence '{key}' was not declared true for this turn. {message}"]
        return _check

    add("H8", "Step 0.0 language self-check performed fresh this turn", "HARD", 5,
        always,
        evidence_check("step0_language_checked",
                        "Compare the user's current-message language against the "
                        "explanation text just drafted; declare true only after doing it."))

    add("H9", "Step 5a compatibility verified this turn", "HARD", 5,
        not_lightweight,
        evidence_check("step5a_compatibility",
                        "Re-read/re-verify compatibility from the MCP response before rendering."))

    add("H10", "Step 5b calculate_psu.py actually run", "HARD", 5,
        not_lightweight,
        evidence_check("step5b_psu", "Run scripts/calculate_psu.py and compare wattage."))

    add("H11", "Step 5c value/swap comparison considered", "HARD", 3,
        not_lightweight,
        evidence_check("step5c_value_compare", "Consider a better-value swap per Step 5c."))

    add("H12", "Step 5d stock status checked", "HARD", 3,
        not_lightweight,
        evidence_check("step5d_stock", "Check the stock field (or confirm it's absent)."))

    add("H13", "No files borrowed from a sibling skill", "HARD", 4,
        always,
        evidence_check("no_borrowed_files",
                        "Confirm mcp_client.py/calculate_psu.py used were this skill's own files."))

    add("H14", "render_build.py's output included verbatim (Markdown path)", "HARD", 5,
        lambda ctx: not ctx["lightweight"] and ctx["fmt"] == "markdown",
        lambda ctx: check_rendered_block_verbatim(
            ctx["text"], ctx["rendered_block"], ctx["fmt"], ctx["lightweight"]))

    add("H15", "Generated file (if any) was actually delivered/surfaced to the user", "HARD", 2,
        lambda ctx: ctx["produced_file"],
        evidence_check("file_presented",
                        "A file was produced this turn — it must be surfaced via this "
                        "platform's file-delivery mechanism (e.g. present_files), not just "
                        "referenced as plain text. A file the user cannot open is a failed "
                        "delivery even if the content itself was correct."))

    add("H16", "Build-vs-upgrade meta-question handled internally, not relayed", "HARD", 1,
        lambda ctx: ctx["upgrade_question_seen"],
        evidence_check("upgrade_meta_question_handled",
                        "Per SKILL.md's Scope carve-out: answer 'new build' internally and "
                        "re-call with that framing, don't ask the user."))

    # ---- SOFT, advisory only (weight sum = 25) ----
    def soft_text_check(ctx):
        # crude substantiveness heuristic: rationale/explanation prose
        # (everything outside table/card-marker lines) should exist and not
        # be a one-liner. This never blocks sending — it's visibility only.
        non_card_words = 0
        for line in ctx["text"].splitlines():
            stripped = line.strip()
            if not stripped or HEADING_OR_TABLE_RE.match(stripped):
                continue
            if any(re.search(m, stripped, re.IGNORECASE) for m in CARD_LINE_MARKERS):
                continue
            non_card_words += len(stripped.split())
        if non_card_words < 25:
            return [f"Rationale/explanation text looks thin ({non_card_words} words outside "
                    "the card/table) — Step 6 expects a real explanation, not just a price line."]
        return []

    add("S1", "Step 6 rationale reads as substantive (soft heuristic)", "SOFT", 10,
        not_lightweight, soft_text_check)

    def educational_note_check(ctx):
        ev = ctx["evidence"]
        if ev.get("step8_applicable") is not True:
            return []  # not applicable this turn, full credit
        if ev.get("step8_present") is True:
            return []
        return ["--evidence marked step8_applicable=true but step8_present is not true — "
                "an educational note was warranted but not declared as included."]

    add("S2", "Step 8 educational note present when applicable", "SOFT", 5,
        not_lightweight, educational_note_check)

    def aftersales_check(ctx):
        if ctx["lightweight"] or ctx["skip_disclaimer"]:
            return []
        lowered = ctx["text"].lower()
        keywords = ["warranty", "return", "upgrade path", "upgrade in", "years from now",
                    "down the line"]
        if any(k in lowered for k in keywords):
            return []
        return ["No warranty/return or upgrade-path note detected — Step 10 expects one "
                "for a full-build presentation (soft heuristic, may be a false negative)."]

    add("S3", "Step 10 aftersales/upgrade note present", "SOFT", 6,
        not_lightweight, aftersales_check)

    def swap_reprocess_check(ctx):
        if not ctx["is_swap"]:
            return []
        ev = ctx["evidence"]
        if ev.get("swap_full_reprocessed") is True:
            return []
        return ["--is-swap was passed but --evidence 'swap_full_reprocessed' is not true — "
                "Step 9 requires re-running 5a/5b on the WHOLE modified config, not patching "
                "just the changed line."]

    add("S4", "Swap/add/remove triggered a full reprocess, not an incremental patch", "SOFT", 4,
        lambda ctx: ctx["is_swap"], swap_reprocess_check)

    return rules


# =============================================================================
# Main
# =============================================================================

def parse_evidence(raw, raw_file):
    if raw_file:
        with open(raw_file, "r", encoding="utf-8") as f:
            raw = f.read()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: --evidence is not valid JSON: {e}")
        sys.exit(2)
    if not isinstance(data, dict):
        print("ERROR: --evidence must be a JSON object of booleans.")
        sys.exit(2)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", help="Read draft text from this file instead of stdin.")
    parser.add_argument("--lightweight", action="store_true",
                         help="This turn never reached Step 9 (simple Q&A).")
    parser.add_argument("--skip-disclaimer", action="store_true")
    parser.add_argument("--claude-env", choices=["yes", "no"],
                         help="Required unless --lightweight.")
    parser.add_argument("--format", choices=["markdown", "card"], dest="fmt",
                         help="Required unless --lightweight.")
    parser.add_argument("--markdown-fallback-reason", default="")
    parser.add_argument("--rendered-block", default=None,
                         help="The exact stdout of render_build.py for this turn "
                              "(required for --format markdown unless --lightweight).")
    parser.add_argument("--rendered-block-file", default=None,
                         help="Path to a file containing render_build.py's stdout for "
                              "this turn — preferred over --rendered-block for multi-line "
                              "content to avoid shell-quoting issues.")
    parser.add_argument("--produced-file", action="store_true",
                         help="Pass if this turn generated a file the user must open.")
    parser.add_argument("--upgrade-question-seen", action="store_true")
    parser.add_argument("--is-swap", action="store_true")
    parser.add_argument("--evidence", default="",
                         help="JSON object of booleans, e.g. "
                              "'{\"step5a_compatibility\": true}'.")
    parser.add_argument("--evidence-file", default="")
    args = parser.parse_args()

    if not args.lightweight:
        missing = []
        if not args.claude_env:
            missing.append("--claude-env")
        if not args.fmt:
            missing.append("--format")
        if missing:
            print(f"ERROR: {', '.join(missing)} required unless --lightweight is passed.")
            sys.exit(2)

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("ERROR: no input text provided (empty stdin/file).")
        sys.exit(2)

    evidence = parse_evidence(args.evidence, args.evidence_file)

    rendered_block = None
    if args.rendered_block_file:
        try:
            with open(args.rendered_block_file, "r", encoding="utf-8") as f:
                rendered_block = f.read()
        except OSError as e:
            print(f"ERROR: could not read --rendered-block-file: {e}")
            sys.exit(2)
    elif args.rendered_block is not None:
        rendered_block = args.rendered_block

    ctx = dict(
        text=text,
        claude_env=(args.claude_env == "yes"),
        fmt=args.fmt,
        markdown_fallback_reason=args.markdown_fallback_reason,
        lightweight=args.lightweight,
        skip_disclaimer=args.skip_disclaimer or args.lightweight,
        produced_file=args.produced_file,
        upgrade_question_seen=args.upgrade_question_seen,
        is_swap=args.is_swap,
        evidence=evidence,
        rendered_block=rendered_block,
    )

    rules = build_rules()

    hard_failures = []   # list of (rule, [messages])
    soft_failures = []
    score = 0
    max_score = 0

    for rule in rules:
        if not rule["applicable"](ctx):
            # Not applicable this turn — full credit, noted as N/A.
            score += rule["weight"]
            max_score += rule["weight"]
            continue
        max_score += rule["weight"]
        failures = rule["check"](ctx) or []
        if failures:
            if rule["category"] == "HARD":
                hard_failures.append((rule, failures))
            else:
                soft_failures.append((rule, failures))
        else:
            score += rule["weight"]

    print(f"Score: {score}/{max_score} (advisory — see note below)\n")

    if soft_failures:
        print("Soft/advisory notes (do NOT block sending):")
        for rule, failures in soft_failures:
            for f in failures:
                print(f"  [{rule['id']}] {rule['name']}: {f}")
        print()

    if hard_failures:
        print("FAILED — the following HARD rules block sending, regardless of score above:")
        i = 0
        for rule, failures in hard_failures:
            for f in failures:
                i += 1
                print(f"  {i}. [{rule['id']}] {rule['name']}: {f}")
        print("\nFix every item above and re-run. A high score does not offset a single "
              "HARD failure — see reference/compliance_rules.md.")
        sys.exit(1)
    else:
        print("ALL HARD CHECKS PASSED — safe to send as drafted.")
        sys.exit(0)


if __name__ == "__main__":
    main()
