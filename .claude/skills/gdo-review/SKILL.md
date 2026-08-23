---
name: gdo-review
description: Review an in-review ticket's PR via the gdo-reviewer agent, and drive the revise/re-review loop with gdo-implementer up to the attempt cap - approve and merge on a clean pass, or escalate to the user when attempts run out. Use to process a ticket sitting at in-review.
user-invocable: true
allowed-tools: Read, Glob, Bash(python .claude/scripts/gdo_board.py:*), Bash(git add:*), Bash(git commit:*), Bash(gh pr view:*), Bash(gh pr merge:*), Agent, AskUserQuestion
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
   `isolation: "worktree"`) with the ticket ID and `pr_url`. If the custom
   agent type isn't loaded this session, instruct it to read and follow
   `.claude/agents/gdo-reviewer.md` directly, same as `/gdo-implement` does
   for the implementer.

2. **APPROVE →** merge and stop:
   - `gh pr merge <pr-url> --squash --delete-branch`
   - `git pull --rebase origin main` — the squash-merge just advanced
     `origin/main` independently of the local checkout; skip this and the
     next push gets rejected as non-fast-forward.
   - `python .claude/scripts/gdo_board.py set-status <ID> merged`, then
     `git add tasks/ && git commit -m "<ID>: merged"`, then `git push`.
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
   - **Otherwise**: `set-status <ID> in-progress`, commit, then spawn
     `gdo-implementer` (or `gdo-artist`, if this item lives in
     `tasks/art/`) (`Agent`, `isolation: "worktree"`) on the **same
     branch** — tell it explicitly to check out the existing
     `ticket/<ID>-<slug>` branch from `origin`, not create a new one — and
     include the reviewer's findings verbatim as the feedback to address.
     On success, `set-status <ID> in-review`, commit, and go back to step 1
     for a fresh review pass.

## Ground rules

- Never merge on anything short of a clean `APPROVE`.
- Never spawn a 4th implementer attempt past the cap without the user
  explicitly asking for it in the moment.
- Commit every status transition before the next `Agent` spawn — worktree
  isolation forks from committed git state, not uncommitted working-tree
  changes (see `CLAUDE.md`).
- Findings passed to a re-spawned implementer must be the reviewer's actual
  findings, complete — don't summarize them down to a one-liner.
