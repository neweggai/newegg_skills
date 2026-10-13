# Invocation reinforcement snippet — for the caller, not the skill body

Everything in `SKILL.md` (the `<must_follow>` block, the Execution
Contract, the Pre-render/Pre-send gates) is written for the model
*executing* this skill. This file is different: it's text for **whoever
is invoking the skill** — a person typing into AngX (or any other
platform), or an orchestrating prompt calling this skill programmatically
— to paste into their own request when that platform's underlying model
has a track record of skipping this skill's mandatory steps.

This exists because of a real, specific incident: AngX's own model, after
being shown exactly which steps it had skipped, concluded on its own that
restating the contract explicitly in the user's own turn — not just
relying on the skill body — was worth trying, and drafted the wording
below itself. It matched this skill's actual contract accurately, so it's
kept close to that original wording rather than rewritten.

**Why this might help even though the skill body already says all of
this**: some models weight an instruction differently depending on
*where* it appears — a system-loaded skill's own contract versus the same
requirement restated in the human's own message can land with different
salience depending on the underlying model, for reasons this skill has no
visibility into from the outside. This snippet is a way to test that,
cheaply, without changing the skill itself. It is not a fix for a model
that doesn't reliably follow instructions from *any* position — if this
doesn't move the needle either, that's evidence the gap is in the
platform's own execution discipline, not in wording placement, and the
next lever is a platform-side hook (see SKILL.md's Cross-Platform
Portability section), not another rewording pass.

## Long version (Chinese — as AngX itself drafted it, verbatim)

> 请严格按照 `newegg-pc-builder-v2` 的完整执行契约处理本次全新装机需求。所有
> REQUIRED 步骤必须按顺序实际执行，CONDITIONAL 步骤必须明确判断；不得把讨论草案
> 当作最终结果。最终完整配置必须由该 Skill 自带的 `scripts/render_build.py`
> 原样生成，包含有效商品链接、Add to cart、价格明细、兼容性和功耗结论、库存状态
> 及区块内免责声明。发送前必须对完全相同的最终文本运行该 Skill 自带的
> `scripts/compliance_gate.py`，只有打印 `ALL HARD CHECKS PASSED` 才能发送；
> 通过后不得修改文本。若任一步失败、替换件未真正落实、库存不明或验证不确定，请停止
> 并如实说明，不得猜测、手写配置或宣称已验证。

## Short version (Chinese)

> 严格执行 `newegg-pc-builder-v2` 全流程。不要给草案；只有在 `render_build.py`
> 生成最终配置且同一文本通过 `compliance_gate.py` 的
> `ALL HARD CHECKS PASSED` 后才回复，否则报告未完成。

## Short version (English, same content)

> Execute the full `newegg-pc-builder-v2` contract strictly. Do not return a
> draft. Only reply once `render_build.py` has generated the final
> configuration and that exact text has passed `compliance_gate.py` with
> `ALL HARD CHECKS PASSED` — otherwise report that the turn is incomplete.

## The one clause worth keeping even if you trim everything else

> Only send once the exact final text has passed `compliance_gate.py` —
> and never modify the text after it passes.

This is the same rule as `<must_follow>` rule 7 and Execution Contract
rule 5 in `SKILL.md`, just stated at the point where a caller's own
message is the thing being read, instead of the skill body.
