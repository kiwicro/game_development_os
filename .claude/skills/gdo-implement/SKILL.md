---
name: gdo-implement
description: Manually run the gdo-implementer agent against a single ticket - implement, commit, push, open a real GitHub PR. Use when the user wants to implement one specific ticket right now, outside of full epic autonomy (which /gdo-run will provide once it exists).
user-invocable: true
allowed-tools: Read, Glob, Bash(python .claude/scripts/gdo_board.py:*), Agent, AskUserQuestion
---

# /gdo-implement — Single-Ticket Implementation

Arguments passed: `$ARGUMENTS` — a ticket ID, e.g. `TICKET-004`.

This is the manual, one-ticket-at-a-time trigger for the same implementer
agent `gdo-orchestrator` uses per-item inside its epic loop. Useful for
testing the pipeline and for handling one item ad hoc without spinning up
full autonomy.

## Steps

1. If `$ARGUMENTS` is empty, ask which ticket.
2. Locate the item file — `tasks/tickets/<ID>-*.md`, `tasks/bugs/<ID>-*.md`,
   or `tasks/art/<ID>-*.md` via Glob (an `ART-` ID lives in the last one).
   If not found, say so and stop. **Which directory it's in decides which
   agent you spawn in step 5** — `gdo-artist` for `tasks/art/`,
   `gdo-implementer` for the other two. Same steps either way otherwise.
3. Read it. Check `status`:
   - `backlog` or `ready` → normal case, continue.
   - `done`, `merged`, `qa`, `in-review`, `in-progress` → this ticket is
     already past this stage. Confirm with the user (AskUserQuestion)
     before re-running — re-implementing a done ticket is occasionally
     intentional (rework) but should never happen by accident.
   - `blocked` → check why (`python .claude/scripts/gdo_board.py board
     --epic <its epic>`). If it's blocked on an unmet dependency, tell the
     user and stop — don't force past a real dependency. If it's blocked
     on exhausted attempts, confirm with the user before retrying.
4. `python .claude/scripts/gdo_board.py start <ID>` — moves
   `backlog`/`ready` → `in-progress` **and commits**, in one call. The
   commit is not optional bookkeeping: `Agent` calls with
   `isolation: "worktree"` fork from committed git state, so a spawned
   agent would otherwise read a stale status. Add `--force` only if step
   3's confirmation covered an out-of-sequence case.
5. Spawn the agent decided in step 2 (`Agent` tool,
   `isolation: "worktree"`) with a **`## Brief`** built per the format in
   `.claude/conventions.md` — item ID and file path, epic, branch name, PR
   (none yet), default branch, the ticket body **verbatim**, the contents
   of `.claude/conventions.md`, and `docs/engine.md` if it exists. A Brief
   is not a summary: paraphrasing the acceptance criteria just forces the
   agent to open the file anyway, which is the cost the Brief exists to
   remove.
   Also tell it to read and follow `.claude/agents/gdo-implementer.md` or
   `.claude/agents/gdo-artist.md` (matching which one you're spawning) for
   its full operating instructions if it isn't already running as that
   named agent type — this keeps the skill correct in a session where the
   custom agent type hasn't been (re)loaded.
6. On a report with a PR URL:
   `python .claude/scripts/gdo_board.py opened <ID> --pr-url <URL>`
   (sets `in-review`, records the URL, commits — one call). Tell the user
   the PR URL and a short summary of what was implemented and verified.
   Leave the PR open — this skill never merges on its own; `/gdo-review`
   handles that.
7. On an escalation (agent reported it couldn't proceed) or any failure:
   do **not** advance the status past `in-progress`. Report exactly what
   the agent said blocked it, and ask the user how to proceed — don't retry
   automatically. Automatic retry-with-feedback is `/gdo-review`'s job, once
   a review pass has actually generated that feedback.

## Ground rules

- Never set `status: done`, `merged`, or `qa` from this skill — those only
  happen after a real review/merge/QA pass, which don't exist yet as of
  this skill. The furthest this skill takes a ticket is `in-review`.
- Don't touch any ticket other than the one requested.
