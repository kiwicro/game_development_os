---
name: gdo-review
description: Review an in-review ticket's PR via the gdo-reviewer agent, and drive the revise/re-review loop with gdo-implementer up to the attempt cap - approve and merge on a clean pass, or escalate to the user when attempts run out. Use to process a ticket sitting at in-review.
user-invocable: true
allowed-tools: Read, Glob, Bash(python .claude/scripts/gdo_board.py:*), Bash(gh pr view:*), Agent, AskUserQuestion
---

# /gdo-review — PR Review & Iterate Loop

Arguments passed: `$ARGUMENTS` — a ticket ID, e.g. `TICKET-002`.

This is the manual trigger for the same review/iterate cycle the full
orchestrator (`gdo-orchestrator`, via `/gdo-run`) runs automatically per
item. It pairs with `/gdo-implement`, which gets an item to `in-review` —
this skill takes it from there to `merged` or an escalation.

## Preconditions

Locate the item (`tasks/tickets/<ID>-*.md`, `tasks/bugs/<ID>-*.md`, or
`tasks/art/<ID>-*.md`). Require `status: in-review` and a non-null
`pr_url`. If not met, say why and stop — e.g. `backlog`/`ready` means
`/gdo-implement` hasn't run yet. Note which directory it's in — that
decides which agent gets re-spawned in step 3 below if it's rejected.

## The loop

Repeat up to **3 rejection cycles** (i.e. up to 3 `REQUEST_CHANGES`
verdicts before giving up — a 4th attempt is never spawned automatically):

1. **Review.** Spawn the `gdo-reviewer` agent (`Agent` tool,
   `isolation: "worktree"`, **`model: "opus"`** — pass it explicitly, see
   *Models* in `.claude/conventions.md`) with a **`## Brief`** per
   `.claude/conventions.md` — including the `pr_url` and the ticket body
   verbatim. If the custom agent type isn't loaded this session, instruct
   it to read and follow `.claude/agents/gdo-reviewer.md` directly, same as
   `/gdo-implement` does for the implementer.

2. **APPROVE →** merge and stop:
   - `python .claude/scripts/gdo_board.py land <ID>` — one call for the
     whole sequence: it guards the branch against `tasks/**` edits,
     squash-merges with `--delete-branch`, `pull --rebase`s (the
     squash-merge advances `origin/main` independently of the local
     checkout, so skipping that gets the next push rejected as
     non-fast-forward), sets `merged`, commits, and pushes.
   - If `land` **rejects** the branch for modifying `tasks/`, that is a real
     process violation, not a hiccup — the implementer wrote board state it
     should not have. Report it to the user rather than forcing past it;
     `--force` skips the guard and re-opens exactly the merge conflict the
     guard exists to prevent.
   - Report the merge to the user, including the reviewer's acceptance-
     criteria verification. Mention that `/gdo-qa-run` is the next stage —
     `merged` is as far as this skill itself takes it.

3. **REQUEST_CHANGES →** read the ticket's current `attempts` value, then:
   - `python .claude/scripts/gdo_board.py set-status <ID> changes-requested
     --attempts <current+1>`, commit that change.
   - **If the new `attempts` reached 3**: `set-status <ID> blocked`, commit,
     and stop the loop — report the full findings history to the user and
     say plainly that automatic iteration is exhausted; ask how they want
     to proceed (more manual guidance, override and merge anyway, or drop
     the ticket). Do not spawn a 4th implementer attempt on your own.
   - **Otherwise**: `python .claude/scripts/gdo_board.py start <ID>`
     (`changes-requested` → `in-progress`, committed), then spawn
     `gdo-implementer` (or `gdo-artist`, if this item lives in
     `tasks/art/`) (`Agent`, `isolation: "worktree"`, `model: "sonnet"` /
     `model: "haiku"` respectively) with a `## Brief`
     whose **Branch** line says the branch already exists on `origin` —
     check it out and continue, do NOT create a new one — and whose
     **Feedback to address** section carries the reviewer's findings
     verbatim. On success, `python .claude/scripts/gdo_board.py opened <ID>
     --pr-url <same URL>`, then go back to step 1 for a fresh review pass.

## Ground rules

- Never merge on anything short of a clean `APPROVE`.
- Never spawn a 4th implementer attempt past the cap without the user
  explicitly asking for it in the moment.
- Use `start`/`opened`/`land` rather than `set-status` plus hand-rolled
  git — they commit at the right moments, which worktree isolation depends
  on, and `land` gets the merge/rebase/push ordering right.
- Findings passed to a re-spawned implementer must be the reviewer's actual
  findings, complete — don't summarize them down to a one-liner.
