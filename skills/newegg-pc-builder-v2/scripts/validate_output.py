#!/usr/bin/env python3
"""
Pre-send output validator for the newegg-pc-builder-v2 skill.

Purpose: the Step 9 "pre-send gate" in SKILL.md was a text-only checklist —
the LLM was supposed to re-read its own draft and self-certify four items.
That has failed in practice on non-Claude platforms (e.g. AngX dropped the
disclaimer twice), because "read the rule" and "actually executed it" are
not the same thing for a model that treats a written checklist as
optional. This script moves the check from prose into code: the agent
pipes its drafted response text in, and gets a pass/fail verdict it can
actually act on, instead of relying on its own re-reading.

This does NOT replace human/LLM judgment on content quality (rationale,
correctness of prices, etc.) — it only checks for the mechanical items
that have actually been observed missing:
  1. No leaked internal-process / environment-detection narration
  2. Add to cart link/button present
  3. No CJK (or other non-ASCII-letter) text on card/table lines
  4. The disclaimer line present (for full-build presentations)
  5. Declared environment and declared output format actually match
     (added after a real recurring failure: a Claude session with
     visualize:show_widget available still shipped a plain Markdown
     table instead of the mandatory HTML card — see SKILL.md Step 9).

Check 5 is why --claude-env and --format are now REQUIRED, not optional.
The whole point is that you cannot silently skip stating the environment
you detected — the script forces you to write it down every single call,
then cross-checks it against what you actually produced. Passing the
wrong pair (e.g. --claude-env yes --format markdown with no
--markdown-fallback-reason) is a hard failure, not a warning.

Usage:
  python3 scripts/validate_output.py --claude-env yes --format card < draft.txt
  python3 scripts/validate_output.py --claude-env no  --format markdown < draft.txt
  python3 scripts/validate_output.py --claude-env yes --format markdown \
      --markdown-fallback-reason "widget call errored: <error>" < draft.txt
  python3 scripts/validate_output.py --file draft_response.txt --claude-env yes --format card
  python3 scripts/validate_output.py --skip-disclaimer --claude-env yes --format card
                                                          # for lightweight
                                                          # single-item Q&A
                                                          # that never
                                                          # triggers Step 9

--claude-env: yes/no — state plainly what the LIVE tool-list check found
  THIS turn (visualize:show_widget present or not). Never reuse a value
  from an earlier call or an earlier conversation.
--format: markdown/card — which artifact you're piping in. For "card",
  pipe in the widget_code HTML itself (not surrounding chat prose). For
  "markdown", pipe in the chat-visible Markdown block.
--markdown-fallback-reason: only needed when claude-env=yes and
  format=markdown at the same time — per SKILL.md, that combination is
  only legitimate when the widget call itself errored at runtime. State
  the actual error; an empty/generic reason still fails.

Exit code 0 + "ALL CHECKS PASSED" only when every applicable check passes.
Exit code 1 + a list of specific failures otherwise — fix the draft and
re-run; do not send until this prints ALL CHECKS PASSED.
"""

import sys
import re
import argparse

# ---------------------------------------------------------------------------
# Check 1: leaked internal-process / environment-detection narration
# ---------------------------------------------------------------------------
# Phrases observed in real failures, plus generalizations of the same
# pattern. Case-insensitive; matches on substrings so minor rewording is
# still caught.
BANNED_NARRATION_PATTERNS = [
    r"utm_source\s*=",                     # literal internal variable
    r"runtime environment",
    r"platform signal",
    r"no claude[- ]exclusive tool",
    r"claude[- ]exclusive tool",
    r"comboCompatibleAll",
    r"calculate_psu\.py",
    r"mcp_client\.py",
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
    # Embedded mid-rationale narration (not just preamble) — e.g. audit
    # trail language justifying a price/data point by referencing process
    # or prior turns, instead of just stating the product fact.
    r"延续.{0,8}(上一轮|上次|之前)",
    r"上一轮同样的情况",
    r"并非配置出错",
    r"没有虚标",
    r"数据快照",
    r"按实价呈现",
    r"我按实价",
    r"没有.{0,4}替换",
]

# ---------------------------------------------------------------------------
# Check 2: Add to cart
# ---------------------------------------------------------------------------
ADD_TO_CART_PATTERNS = [
    r"add to cart",                        # button/link copy, case-insens.
    r"secure\.newegg\.com/api/shop/add",   # the actual cart URL
    r"openLink\(",                         # card button handler
]

# ---------------------------------------------------------------------------
# Check 3: non-English content on card/table lines
# ---------------------------------------------------------------------------
# Heuristic: a line is "card/table region" if it looks like a markdown
# table row, or contains one of the fixed English card labels/badges that
# should never be mixed with other-language text.
CARD_LINE_MARKERS = [
    r"^\s*\|",                             # markdown table row
    r"compatibility verified",
    r"power headroom",
    r"combo savings",
    r"promo code savings",
    r"recommended build",
    r"out of stock",
]

# Matches actual foreign-script letters (Chinese/Japanese/Korean, Cyrillic,
# Arabic, etc.) — NOT general non-ASCII, since the card templates
# legitimately use an em dash (—), checkmarks (✅), and a warning triangle
# (⚠️) as approved punctuation/icons. Only real foreign-language text is a
# violation; typographic symbols are not.
FOREIGN_SCRIPT_RE = re.compile(
    r"["
    r"\u4E00-\u9FFF"    # CJK Unified Ideographs (Chinese/Japanese kanji)
    r"\u3040-\u30FF"    # Hiragana + Katakana
    r"\u3400-\u4DBF"    # CJK Extension A
    r"\uAC00-\uD7A3"    # Hangul syllables (Korean)
    r"\u3000-\u303F"    # CJK punctuation (、。「」etc.)
    r"\uFF00-\uFFEF"    # Fullwidth forms
    r"\u0400-\u04FF"    # Cyrillic
    r"\u0600-\u06FF"    # Arabic
    r"]"
)

# ---------------------------------------------------------------------------
# Check 4: disclaimer
# ---------------------------------------------------------------------------
DISCLAIMER_REQUIRED_SUBSTRINGS = [
    "subject to change",
    "confirm final pricing",
]

# ---------------------------------------------------------------------------
# Check 5: declared environment vs. declared/actual format must match
# ---------------------------------------------------------------------------
# A literal Markdown pipe-table header, e.g. "| Part | Model | Price |" —
# tolerant of spacing, present regardless of which language the rest of
# the message uses (card/table copy is always English per the skill).
MARKDOWN_TABLE_HEADER_RE = re.compile(
    r"\|\s*part\s*\|\s*model\s*\|\s*price\s*\|", re.IGNORECASE
)
MARKDOWN_TABLE_SEP_RE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")

# Minimal signals that the piped-in content is actually markup, not prose/
# Markdown. Doesn't need to be exhaustive — just enough to catch "this is
# obviously not HTML" mistakes (e.g. pasting the Markdown template while
# claiming --format card).
HTML_MARKUP_MARKERS = [
    r"<div", r"<table", r"<button", r"<span", r"onclick=\"openLink\(",
]


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
                "claude-env=yes but format=markdown with no "
                "--markdown-fallback-reason given. Per SKILL.md Step 9, "
                "the card is mandatory once visualize:show_widget is "
                "confirmed present — Markdown is only a legitimate choice "
                "here if the widget call itself errored at runtime. Either "
                "switch to --format card (and pipe in the widget_code "
                "HTML), or pass --markdown-fallback-reason with the "
                "actual error."
            )

    if not claude_env and fmt == "card":
        failures.append(
            "claude-env=no but format=card. The HTML card only renders "
            "via visualize:show_widget, which this call declares is not "
            "available in this environment. Use --format markdown instead "
            "— it's the required universal baseline for non-Claude "
            "platforms."
        )

    if fmt == "card":
        if not has_html_markup:
            failures.append(
                "format=card was declared but no HTML markup "
                "(<div>/<table>/<button>/openLink(...)) was found in the "
                "piped-in content. Pipe in the actual widget_code HTML, "
                "not chat prose or a Markdown table."
            )
        if has_md_table:
            failures.append(
                "format=card was declared but the content contains a "
                "Markdown pipe-table row/header. This looks like the "
                "Markdown template was pasted by mistake instead of the "
                "HTML card."
            )

    if fmt == "markdown" and has_html_markup and not has_md_table:
        failures.append(
            "format=markdown was declared but the content looks like HTML "
            "card markup with no Markdown table found. If this is really "
            "the Claude card, re-run with --format card instead."
        )

    return failures


def check_narration(text):
    failures = []
    for line in text.splitlines():
        # A line containing an actual URL legitimately has
        # "utm_source=claude" etc. in it — that's a real tracking
        # parameter, not leaked narration. Only check non-URL lines.
        if "http://" in line or "https://" in line:
            continue
        lowered = line.lower()
        for pat in BANNED_NARRATION_PATTERNS:
            if re.search(pat, lowered, flags=re.IGNORECASE):
                failures.append(
                    f"Leaked internal-process narration matched pattern "
                    f"{pat!r} on line: {line.strip()!r}"
                )
    return failures


# ---------------------------------------------------------------------------
# Check 1b: preamble before the build heading/table (structural, not
# keyword-based)
# ---------------------------------------------------------------------------
# Keyword matching (check_narration above) only catches phrasings already
# seen — it's whack-a-mole by nature, and has already been bypassed once
# by a reworded version of the same violation ("cursor/env 信号" instead of
# "平台信号", "整理并输出最终配置" instead of "呈现最终方案"). This check
# instead targets the *structural* signature shared by every observed
# instance: the leaked narration always shows up as a paragraph BEFORE the
# build heading/table, regardless of its exact wording. Every correct
# example in this skill's own reference templates leads straight with the
# build (heading or table) — rationale (Step 6) comes after, never before.
HEADING_OR_TABLE_RE = re.compile(r"^\s*(#{1,3}\s|\|)")


def check_preamble(text, fmt):
    # Markdown-only: this check looks for text before a "#"-heading or a
    # "|"-table row, which is meaningless for HTML card content (an HTML
    # widget legitimately has no markdown headings/pipes at all, so this
    # would otherwise flag the entire card as "preamble" every time).
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
        joined = " / ".join(preamble_lines)
        return [
            "Text found BEFORE the build heading/table (structural check, "
            "independent of wording): "
            f"{joined!r}. Step 9 output must lead with the build itself — "
            "no preamble about environment, tools, data readiness, or "
            "process. If this is genuinely Step 0's clarifying question "
            "(no build being sent yet), this check doesn't apply — only "
            "run this validator against a drafted FULL BUILD response."
        ]
    return []


def check_add_to_cart(text):
    for pat in ADD_TO_CART_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            return []
    return ["No Add to cart link/button found (required on every platform, "
            "every full-build presentation)."]


def check_card_language(text):
    failures = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        is_card_line = any(
            re.search(marker, stripped, flags=re.IGNORECASE)
            for marker in CARD_LINE_MARKERS
        )
        if not is_card_line:
            continue
        non_ascii_chars = FOREIGN_SCRIPT_RE.findall(stripped)
        if non_ascii_chars:
            failures.append(
                "Non-English content found on a card/table line: "
                f"{stripped!r}"
            )
    return failures


def check_disclaimer(text, skip):
    if skip:
        return []
    lowered = text.lower()
    if all(s in lowered for s in DISCLAIMER_REQUIRED_SUBSTRINGS):
        return []
    return ["Disclaimer line not found (expected wording containing "
            "'subject to change' and 'confirm final pricing'). Required "
            "for every full-build presentation on every platform. Pass "
            "--skip-disclaimer only for lightweight single-item Q&A that "
            "never triggers Step 9."]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="Read draft response from this file "
                                        "instead of stdin.")
    parser.add_argument("--skip-disclaimer", action="store_true",
                         help="Skip the disclaimer check for lightweight "
                              "single-item Q&A responses that don't "
                              "trigger Step 9's full presentation.")
    parser.add_argument("--claude-env", required=True, choices=["yes", "no"],
                         help="State what the LIVE tool-list check found "
                              "THIS turn: is visualize:show_widget present? "
                              "Required — never reused from a prior call.")
    parser.add_argument("--format", required=True,
                         choices=["markdown", "card"],
                         help="Which artifact is being piped in: the "
                              "chat-visible Markdown block, or the "
                              "widget_code HTML for the card.")
    parser.add_argument("--markdown-fallback-reason", default="",
                         help="Required only when --claude-env yes is "
                              "combined with --format markdown — state "
                              "the runtime error that forced the "
                              "Markdown fallback.")
    args = parser.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("ERROR: no input text provided (empty stdin/file). Pipe the "
              "drafted response in before sending it.")
        sys.exit(2)

    claude_env = (args.claude_env == "yes")

    all_failures = []
    all_failures += check_narration(text)
    all_failures += check_preamble(text, args.format)
    all_failures += check_add_to_cart(text)
    all_failures += check_card_language(text)
    all_failures += check_disclaimer(text, args.skip_disclaimer)
    all_failures += check_format_matches_environment(
        text, claude_env, args.format, args.markdown_fallback_reason
    )

    if all_failures:
        print("FAILED — fix the draft and re-run before sending:\n")
        for i, f in enumerate(all_failures, 1):
            print(f"  {i}. {f}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
