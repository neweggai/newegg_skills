# Environment Detection Methods

Load this file only when actually needing to determine `utm_source` (Step
9a) or the Step 9 card-vs-Markdown branch decision. Best-effort, not
guaranteed reliable — there's no standardized cross-platform way for an
Agent to know for certain which tool it's running in. These are heuristic
clues ranked most-to-least trustworthy, not a 100%-accurate check —
misjudgments can happen; never tell the user "I've confirmed the runtime
environment."

**Detection order — stop at the first hit, no need to run all of them:**

1. **Tool-list check (most reliable)**: does the available tool list
   contain a Claude-exclusive tool (`visualize:show_widget`,
   `visualize:read_me`)? If yes → `claude`. Unlikely to be coincidentally
   reused by another platform.
2. **Project-directory signature file (secondary, needs filesystem
   access)**:
   ```bash
   ls -la .cursorrules .cursor/ 2>/dev/null
   ```
   Found → `cursor`. **Precondition**: only meaningful if the skill's
   execution environment can actually see the user's real project
   filesystem (e.g. Cursor's integrated terminal, not an isolated
   sandbox). A sandbox unrelated to the project directory will
   false-negative here — that doesn't mean it's not Cursor.
3. **Environment variables (least reliable, last resort)**:
   ```bash
   env | grep -i -E "cursor|copilot|windsurf"
   ```
   Many tools set nothing identifiable — finding nothing isn't a failed
   check, just no extra signal.
4. **Nothing conclusive** → `unknown_agent`. Never guess a specific
   platform name without evidence — a fabricated guess damages attribution
   data more than an honest "unknown" label.

**No need to run the full chain every time** — if step 1 already confirms
Claude, skip 2 and 3.

## 🚨 Never narrate this process to the user (hard requirement)

This detection runs silently to decide two internal things: the
card-vs-Markdown branch and the `utm_source` value in product links. Never
say which step matched, what tools were or weren't found, what
`utm_source` was resolved to, or that "no platform signal was found." Also
never announce that "all data is ready" or similar before presenting the
build — just present it. This is the same rule as SKILL.md's
no-internal-process-narration section, applied to this specific step; see
that section for the concrete wrong/right example (the AngX case).
