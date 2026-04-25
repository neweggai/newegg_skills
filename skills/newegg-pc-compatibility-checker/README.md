# newegg-pc-compatibility-checker

A Claude skill that verifies whether a set of specific PC hardware items are
compatible with each other, using Newegg's PC Builder compatibility engine.

## What it does

Answers questions like:

- "Will an RTX 5090 work with my 750W power supply?"
- "Can I put this DDR5 RAM on my B550 motherboard?"
- "Is the MSI Z890 motherboard compatible with an AMD 9800X3D?"
- "这套配置能兼容吗？AMD 9800X3D + MSI X870E + G.Skill DDR5 + RM1000x"

The skill routes the user's parts through Newegg's real compatibility API
(`comboCompatibleAll`) and reports the verdict, the specific failing rules,
and a concrete repair path — rather than guessing from the model's own
hardware knowledge.

## How it works

Under the hood, the skill uses Claude's `bash` tool to call two Newegg MCP
endpoints over HTTP/JSON-RPC — no MCP client registration required:

| Endpoint                                                    | Purpose                                     |
| ----------------------------------------------------------- | ------------------------------------------- |
| `https://apis-e111.newegg.org/mcp/endpoint/pc-builder`      | Compatibility check (`comboCompatibleAll`)  |
| `https://apis.newegg.com/ex-mcp/endpoint/product-search`    | Resolve model names → Newegg item numbers  |

Flow:

1. If the user gave model names, call product-search to resolve each name to a
   Newegg `ItemNumber`. If the user gave item numbers directly, skip this step.
2. Call pc-builder's `comboCompatibleAll` with all item numbers
   space-separated in a single `itemNumber` string.
3. Report `isCompatible`. If `false`, walk through every `reasonTrace` and
   propose a concrete replacement part, then re-verify with pc-builder.

## Key design rules

- **Never guess compatibility from the model's own knowledge.** Every verdict
  comes from pc-builder.
- **Re-verify after every proposed fix.** A suggestion is not valid until
  pc-builder returns `isCompatible: true` for the updated combination.
- **Reply in the user's language.** Chinese question → Chinese reply. English
  question → English reply. The English `reasonTraces` stay in parentheses for
  reference.
- **Do not silently substitute parts.** If product-search returns zero results
  for a part, tell the user and ask — do not proceed with a similar part.
- **Disclose the PSU wattage limitation.** pc-builder checks sockets,
  chipsets, memory generations, and physical fit — but it does not validate
  that a PSU's wattage meets the GPU manufacturer's recommended minimum. When
  a PSU is among the compatible items, the skill tells the user to cross-check
  wattage themselves.

## Benchmark

Latest evaluation (iteration 3, `claude-opus-4-7`):

| Metric    | With skill | Without skill | Delta         |
| --------- | ---------- | ------------- | ------------- |
| Pass rate | 91.7%      | 35.3%         | **+56.4 pp**  |

Three eval scenarios: direct item-number check, GPU-upgrade with PSU check,
DDR4/DDR5 generation mismatch.

## Installation

### As a Claude Code skill

Clone this repo into your local skills folder:

```bash
git clone git@git.newegg.org:global-ai/skills-center/newegg-pc-compatibility-checker.git ~/.claude/skills/newegg-pc-compatibility-checker
```

Restart Claude Code. The skill auto-triggers on compatibility-related
questions.

### As a Cowork plugin

Package this folder into a `.plugin` file:

```bash
zip -r newegg-pc-compatibility-checker.plugin . -x ".git/*" ".specstory/*"
```

Then drag the `.plugin` file into a Cowork session's plugin installer.

## Author

Eric Lin (<eric.d.lin@newegg.com>) — Newegg Global AI team

## License

MIT
