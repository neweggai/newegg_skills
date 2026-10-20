# Product Link Rules (Step 9a)

Load this file only when actually constructing product links for a card or
Markdown table — it's procedural detail, not something to hold in mind for
every request. Referenced from SKILL.md's Step 9.

Every component's title (CPU/motherboard/GPU/RAM/storage/case/PSU model
name) should be clickable, linking to that product's real Newegg page.
Order for obtaining the link:

1. **Prefer a link/URL field already in the MCP response** (field name
   varies — `url`, `link`, `productUrl`, `itemUrl`, etc. Don't assume a
   fixed name; check what the response actually returned). **Even a
   response-provided link still needs the UTM parameters from step 3
   appended.**
2. **If only an item number is available**, construct based on its format
   (both formats produce a real working link — never skip just because the
   format looks unfamiliar):
   - **Standard hyphenated numeric** (`19-113-938`, shape `XX-XXX-XXX`):
     strip hyphens → `19113938`, prepend `N82E168` →
     `https://www.newegg.com/p/N82E16819113938`
   - **Marketplace/other format** (contains letters or different length,
     e.g. `2AM-000Z-000D6`, `9SIAG98KRK3386`, `1HU-024C-000C2`): keep
     as-is (uppercase, hyphens intact), append directly after `/p/` →
     `https://www.newegg.com/p/2AM-000Z-000D6`. Newegg's routing accepts a
     bare item number with no slug required. This is a different
     construction method, not a reason to skip the link.
3. **Always append `Item=` and UTM parameters, fixed order, cannot be
   omitted — applies even to links already provided by the response:**

   ```
   https://www.newegg.com/p/{ItemNumber}?Item={ItemNumber}&utm_source={platform}&utm_medium=ai_skill&utm_campaign=aik_{platform}_pc-builder&utm_content=newegg-pc-builder
   ```

   `Item=` must exactly match the `{ItemNumber}` used in the path (same
   conversion state — both converted, or both as-is). `{platform}` is the
   same value in `utm_source` and inside `utm_campaign`. Examples:
   ```
   https://www.newegg.com/p/9SIAD6HKKM2343?Item=9SIAD6HKKM2343&utm_source=claude&utm_medium=ai_skill&utm_campaign=aik_claude_pc-builder&utm_content=newegg-pc-builder
   https://www.newegg.com/p/N82E16819113844?Item=N82E16819113844&utm_source=cursor&utm_medium=ai_skill&utm_campaign=aik_cursor_pc-builder&utm_content=newegg-pc-builder
   https://www.newegg.com/p/N82E16819113844?Item=N82E16819113844&utm_source=other&utm_medium=ai_skill&utm_campaign=aik_other_pc-builder&utm_content=newegg-pc-builder
   ```

   **UTM values:**
   - **`utm_medium` is fixed**: always `ai_skill`.
   - **`utm_source` is the platform this skill is running on** — determine
     via the method in `reference/environment_detection.md`. Use that
     platform's own name, lowercase. This is based on the **triggering
     platform**, not which model is running — Cursor-on-Claude-backend
     still gets `cursor`.
     - Confirmed Claude environment → `utm_source=claude`
     - Confirmed Cursor environment → `utm_source=cursor`
     - Confirmed another Agent tool → that tool's name, e.g.
       `utm_source=windsurf`
     - Unknown or not identifiable → `utm_source=other`. Never use
       `ai_skill_other` or `unknown_agent`. Never guess a specific
       platform name without evidence.
   - **`utm_campaign`** is `aik_` + the same `{platform}` used in
     `utm_source` + `_pc-builder`. Claude → `aik_claude_pc-builder`;
     Cursor → `aik_cursor_pc-builder`; unknown → `aik_other_pc-builder`.
   - **`utm_content`** stays `newegg-pc-builder`.

   If a response-provided link already has a `?`, append with `&` instead
   of adding a second `?`.
4. **No link, no item number at all** → leave the title as plain text, no
   link. Never fabricate a URL — a wrong link damages trust more than no
   link. (This is different from "unfamiliar format," which still gets a
   link per rule 2.)
5. Links open in a new tab (`target="_blank"`) — don't navigate away in the
   current session and lose the user's conversation context.
6. **Known risk, state honestly if asked**: a marketplace-format item that's
   out of stock/delisted may auto-redirect on Newegg's site to a similar
   replacement, so the link could land on a near-but-not-exact match. This
   is Newegg's own site behavior, not a construction error — if a user says
   "this doesn't look right," explain this rather than assuming the rule is
   broken.
