---
name: gdo-implement
description: Manually run the gdo-implementer agent against a single ticket - implement, commit, push, open a real GitHub PR. Use when the user wants to implement one specific ticket right now, outside of full epic autonomy (which /gdo-run will provide once it exists).
user-invocable: true
allowed-tools: Read, Glob, Bash(python .claude/scripts/gdo_board.py:*), Bash(git commit:*), Bash(git add:*), Agent, AskUserQuestion
---

# /gdo-implement — Single-Ticket Implementation

Arguments passed: `$ARGUMENTS` — a ticket ID, e.g. `TICKET-004`.

This is the manual, one-ticket-at-a-time trigger for the same
`gdo-implementer` agent the full orchestrator (`/gdo-run`, not built yet)
will use per-ticket inside its epic loop. Useful for testing the pipeline
and for handling one ticket ad hoc without spinning up full autonomy.

## Steps

1. If `$ARGUMENTS` is empty, ask which ticket.
2. Locate the ticket file (`tasks/tickets/<ID>-*.md` or
   `tasks/bugs/<ID>-*.md` via Glob). If not found, say so and stop.
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
4. Move status to `in-progress`:
   `python .claude/scripts/gdo_board.py set-status <ID> ready` (only if
   currently `backlog`), then
   `python .claude/scripts/gdo_board.py set-status <ID> in-progress`
   (add `--force` only if step 3's confirmation covered an out-of-sequence
   case). **Then commit that change** (`git add tasks/ && git commit -m
   "<ID>: mark in-progress"`) before the next step — `Agent` calls with
   `isolation: "worktree"` fork from committed git state, not uncommitted
   working-tree changes, so a spawned agent that reads ticket status would
   otherwise see stale data (see `CLAUDE.md`).
5. Spawn the `gdo-implementer` agent (`Agent` tool, `isolation: "worktree"`)
   with a self-contained prompt: the repo is the current working directory,
   the ticket ID is `<ID>`, and — **important** — instruct it to read and
   follow `.claude/agents/gdo-implementer.md` in the repo for its full
   operating instructions if it isn't already running as that named agent
   type (this keeps the skill correct even in a session where the custom
   agent type hasn't been (re)loaded yet).
6. On a report with a PR URL: run
   `python .claude/scripts/gdo_board.py set-status <ID> in-review --pr-url <URL>`,
   then commit that change too. Tell the user the PR URL and a short
   summary of what was implemented and verified. Leave the PR open — this
   skill never merges (no reviewer exists yet to have approved it).
7. On an escalation (agent reported it couldn't proceed) or any failure:
   do **not** advance the status past `in-progress`. Report exactly what
   the agent said blocked it, and ask the user how to proceed — don't retry
   automatically. (Automatic retry-with-feedback is Phase 4's job, once the
   reviewer exists to generate that feedback.)

## Ground rules

- Never set `status: done`, `merged`, or `qa` from this skill — those only
  happen after a real review/merge/QA pass, which don't exist yet as of
  this skill. The furthest this skill takes a ticket is `in-review`.
- Don't touch any ticket other than the one requested.
