---
name: gdo-run
description: Start (or resume) full autonomous execution of an approved epic - implement, review/iterate, merge, QA, repeat, across every ticket, without further prompting. Use when the user wants an epic run end to end. Refuses on an epic that isn't ready/in-progress.
user-invocable: true
allowed-tools: Read, Bash(python .claude/scripts/gdo_board.py:*), Agent, TaskStop
---

# /gdo-run — Autonomous Epic Execution

Arguments passed: `$ARGUMENTS` — an epic ID, e.g. `EPIC-002`.

This is the payoff of the whole pipeline: everything `/gdo-implement`,
`/gdo-review`, and `/gdo-qa-run` do by hand, chained automatically across
an epic's entire ticket queue by the `gdo-orchestrator` agent, until the
epic is done or every remaining ticket is legitimately blocked on something
that needs you.

## Preconditions

Read the epic file. Require `status: ready` or `status: in-progress` (the
latter means a prior `/gdo-run` on this epic didn't finish — resuming is
fine and expected, state is fully persisted in `tasks/` + git). If it's
`draft`: tell the user to approve it via `/gdo-epic` first. If `done`:
tell them it's already finished.

## Running it

Spawn the `gdo-orchestrator` agent: `Agent` tool, **no** `isolation`
parameter (it works directly in the repo's checkout, not a worktree — see
`.claude/agents/gdo-orchestrator.md` for why). If the custom agent type
isn't loaded this session, instruct it to read and follow
`.claude/agents/gdo-orchestrator.md` directly, same fallback pattern as the
other triggers. Give it just the epic ID — it derives everything else from
`tasks/` and `CLAUDE.md` itself.

Tell the user plainly once it's launched: this now runs unattended, you'll
report back when it finishes or when it has something that needs their
decision — don't imply you'll be narrating progress in the meantime, since
you won't see anything until it's done.

## When it reports back

Relay its final report essentially as-is: what's done (with PR links),
what's blocked and why, any bugs filed. If anything is `blocked`, be direct
that it's waiting on a decision — don't soften a real blocker into "minor
follow-up." If everything's `done`, say so plainly and mention `/gdo-board`
if they want the full picture.

## Ground rules

- Don't second-guess or re-run work the orchestrator's report says is
  already done — trust its report the same way you'd trust any other
  sub-agent's, but see `/gdo-board` if you want to independently confirm
  state.
- If the user asks to stop a run that's already in progress, use `TaskStop`
  with the orchestrator's task ID to actually terminate it — don't just
  say you can't. Be clear afterward about the risk: whatever ticket it was
  mid-stage on when stopped may be left in a non-terminal status (e.g.
  `in-progress` with a half-finished implementation, or an open PR that was
  never reviewed) — check `/gdo-board` for that epic afterward and decide
  by hand whether to resume via the single-ticket skills, `/gdo-run` again,
  or clean it up manually.
