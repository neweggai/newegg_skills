# Newegg Link Tagging (UTM)

Same convention as `newegg-pc-builder-v2`'s `reference/product_link_rules.md` — load this
only when actually constructing a Newegg product link, not something to hold in mind for
every request.

Every product link this skill shows must carry attribution tagging:

```
https://www.newegg.com/p/{ItemNumber}?Item={ItemNumber}&utm_source={platform}&utm_medium=ai_skill&utm_campaign=aik_{platform}_ram-openbox&utm_content=newegg-ram-openbox
```

`Item=` must exactly match the `{ItemNumber}` used in the path. If a response already
provides a full link, still append the UTM parameters (with `&` if it already has a `?`,
otherwise `?`) rather than dropping them.

**UTM values** — same convention as pc-builder-v2:

- **`utm_medium` is fixed**: always `ai_skill`.
- **`utm_source` is the platform this skill is running on**, not hardcoded — determine it
  the same way as pc-builder-v2:
  1. A Claude-exclusive tool (e.g. `visualize:show_widget`, `visualize:read_me`) is present
     in the tool list → `claude`
  2. A project-directory signature (`.cursorrules`, `.cursor/`) is visible → `cursor`
  3. An identifying env var (`cursor`/`copilot`/`windsurf`) is set → that platform
  4. Nothing conclusive → `other` — never use `ai_skill_other` or `unknown_agent`, and
     never guess a specific platform without evidence

  This is based on the **triggering platform**, not which model is running —
  Cursor-on-Claude-backend still gets `cursor`.
- **`utm_campaign`** is `aik_` + the same `{platform}` used in `utm_source` + `_ram-openbox`:
  Claude → `aik_claude_ram-openbox`; Cursor → `aik_cursor_ram-openbox`; unknown →
  `aik_other_ram-openbox`.
- **`utm_content`** stays `newegg-ram-openbox`.

No item number at all → leave the title as plain text, no link. Never fabricate a URL.
