# Compliance Gate — Rule Inventory & Weights (Step 9/10, all platforms)

Load this file only if you need to know *why* a specific rule exists or
*why* it carries the weight it does — `scripts/compliance_gate.py` is what
actually runs; this is the audit trail behind it. Referenced from
SKILL.md's Pre-render gate and Pre-send gate sections.

## Why weights exist, and what they don't do

Total weight is 100, split HARD (75) / SOFT (25). **The weight is a
reporting number only — it never lets one rule's pass offset another
rule's failure.** Any single failed HARD rule blocks sending, regardless
of the overall score. A 96/100 score with one HARD rule failed is still a
FAIL. This was a deliberate design choice after a first draft of this idea
(built on AngX) proposed a pure score-threshold gate — that would have let
a small, ignorable-looking miss (say, the disclaimer) get "outvoted" by
everything else going right, which is exactly the failure mode this skill
has actually hit in practice. So: HARD rules are yes/no gates that happen
to carry a weight for visibility; SOFT rules are the only place weight
functions as an actual score.

## HARD rules (75 pts total) — any single failure blocks sending

| ID | Rule | Weight | How it's checked |
|----|------|--------|-------------------|
| H1 | No leaked internal-process narration | 5 | Regex over drafted text |
| H2 | No preamble before the build heading/table | 2 | Structural (text before first `#`/`\|`) |
| H3 | Add to cart link/button present | 7 | Regex over drafted text |
| H4 | Card/table content is English-only | 5 | Regex (foreign-script chars on card-marker lines) |
| H5 | Disclaimer line present | 7 | Regex over drafted text |
| H6 | Declared `--claude-env`/`--format` consistent with each other and the content | 7 | Cross-check declared flags against actual markup found |
| H7 | Product/cart links carry no placeholder tokens and a real `utm_source` | 3 | Regex over URLs in text |
| H17 | Cart link item count matches non-owned component count in the table | 6 | Counts table rows vs. `ItemList` entries in the cart URL, mechanical |
| H8 | Step 0.0 language self-check performed fresh this turn | 5 | `--evidence step0_language_checked` |
| H9 | Step 5a compatibility verified this turn | 5 | `--evidence step5a_compatibility` |
| H10 | Step 5b `calculate_psu.py` actually run | 5 | `--evidence step5b_psu` |
| H11 | Step 5c value/swap comparison considered | 3 | `--evidence step5c_value_compare` |
| H12 | Step 5d stock status checked | 3 | `--evidence step5d_stock` |
| H13 | No files borrowed from a sibling skill | 4 | `--evidence no_borrowed_files` |
| H14 | `render_build.py`'s output included **verbatim** in the final draft (Markdown path) | 5 | Whitespace-normalized substring match against `--rendered-block`/`--rendered-block-file` |
| H15 | Generated file (if any) actually delivered/surfaced to the user | 2 | `--evidence file_presented` (only when `--produced-file`) |
| H16 | Build-vs-upgrade meta-question handled internally, not relayed | 1 | `--evidence upgrade_meta_question_handled` (only when `--upgrade-question-seen`) |

**H17 is new, and directly targets a second recurring AngX failure**: the
cart link and the component table drifting out of sync — a component
quietly dropped from (or left in) the `ItemList` during manual
reassembly, while the table above it still lists the correct parts. This
is fully mechanical: parse the fixed 3-column table, count rows not
marked `owned`/"your existing part", parse the cart URL's `ItemList`,
count its comma-separated entries, and require the two counts to match
exactly. No evidence flag is needed because both sides of the comparison
are already in the text being checked.

**H14 changed from a self-declared flag to a real mechanical check.**
The original version accepted `--evidence render_build_used: true` on
trust. That turned out to be exactly the gap that let the actual
reported failure through: the model *had* run `render_build.py`, could
honestly say so, and then reassembled the message by hand afterward
anyway — dropping the cart link in the process — while still truthfully
declaring the flag. H14 now requires `--rendered-block` or
`--rendered-block-file` containing that turn's actual `render_build.py`
stdout, and fails unless that exact text (whitespace-normalized only —
never reworded) appears verbatim inside the final draft. This is the
single most important change in this revision: it turns "did you use the
render" from a claim into something checked against real evidence in the
same call.

**H15 is the direct fix for the reported AngX failure**: a config was
written to `gaming_pc_build.md` and described in chat, but the platform's
own file-delivery step was never called, so the link/button in that file
was inert. This skill's own Step 9 output is not supposed to require a
separate file-delivery step at all — the core block goes straight into
the chat response — so if `--produced-file` is ever passed, that itself is
worth noticing: it usually means a platform improvised a different
delivery path than this skill specifies, and H15 makes sure that path
didn't silently drop the last step.

**Evidence rules fail closed.** Every `--evidence` key defaults to `false`
if not passed — there is no "assume it happened" branch. This is the same
principle as `--claude-env` already being mandatory in the old
`validate_output.py`: writing a rule in prose and hoping it's followed is
exactly the gap this exists to close, so the script accepts nothing less
than an explicit declaration for each one, every call. H14 goes one step
further than a declaration — see above.

## SOFT rules (25 pts total) — advisory only, never blocks sending

| ID | Rule | Weight | How it's checked |
|----|------|--------|-------------------|
| S1 | Step 6 rationale reads as substantive | 10 | Word-count heuristic outside card/table lines |
| S2 | Step 8 educational note present when applicable | 5 | `--evidence step8_applicable` / `step8_present` |
| S3 | Step 10 aftersales/upgrade note present | 6 | Keyword heuristic (warranty/return/upgrade path) |
| S4 | Swap/add/remove triggered a full reprocess | 4 | `--evidence swap_full_reprocessed` (only when `--is-swap`) |

These exist to surface likely quality gaps (a thin rationale, a missing
upgrade note) without hard-blocking on a heuristic that can have false
positives — a keyword search for "warranty" is a reasonable smoke test,
not a reliable judge of whether Step 10 was actually done well.

## Honest limits (unchanged from the old gate, worth restating)

This script only runs if the agent chooses to call it before sending —
the trigger is still inside the model's own decision loop, the same limit
`validate_output.py` and the original AngX proposal both already
acknowledged. What's different here is what happens *once it's called*:
previously, four things were checked mechanically and everything else
(5a-5d, borrowed-files, render_build.py, file delivery) was a written
instruction with no code behind it at all. Now every hard requirement in
SKILL.md either has a mechanical check or requires an explicit,
per-turn `--evidence` declaration that defaults to failing. That closes
the "silently skipped and nothing noticed" gap; it does not (and can't,
from inside the model's own prompt) close the "chose not to run the gate
at all" gap. The durable fix for that last gap is still a platform-side
hook that runs independent of the model's cooperation — see SKILL.md's
Cross-Platform Portability section.

**A second, related gap this revision closes: the gate approving a draft
that isn't what actually gets sent.** The reported AngX failure wasn't
"the model forgot render_build.py exists" — it had run it, could
honestly declare so, and then reassembled the reply by hand afterward,
dropping the cart link in the process. A flag-based check has no way to
catch that, because the flag was true. H14's move to a verbatim-inclusion
check (checked against the actual `render_build.py` stdout, supplied
alongside the draft) closes that specific hole: it no longer matters
whether the model *used* the render at some point, only whether the exact
text it produced is *still in* the message about to be sent. What this
still can't force: the discipline of piping in the literal final string,
character for character, rather than a draft that gets touched again
afterward. That last mile is, again, a "which text did you feed the
script" question the script itself has no visibility into — same
category of limit as "did you call it at all."
