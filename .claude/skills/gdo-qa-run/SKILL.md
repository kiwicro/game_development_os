---
name: gdo-qa-run
description: Run QA against a merged ticket - re-verify its acceptance criteria on mainline, scoped exploratory pass, file new BUG-NNN tickets for anything found outside scope, reopen the ticket if its own criteria regressed. Use to process a ticket sitting at merged.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Bash(python .claude/scripts/gdo_board.py:*), Bash(git add:*), Bash(git commit:*), Agent, AskUserQuestion
---

# /gdo-qa-run — Post-Merge QA

Arguments passed: `$ARGUMENTS` — a ticket ID, e.g. `TICKET-003`. (Named
`gdo-qa-run` rather than `gdo-qa` to keep it visually distinct from the
`gdo-qa` agent it spawns.)

This is the manual trigger for the same post-merge QA pass the full
orchestrator (`/gdo-run`, Phase 6) will run automatically after every
merge. It's the last stage `/gdo-implement` → `/gdo-review` → this skill
covers before a ticket is genuinely `done`.

## Preconditions

Locate the ticket. Require `status: merged`. If it's anything else, say why
and stop (e.g. `in-review` means `/gdo-review` hasn't approved it yet).

## Running QA

1. Spawn the `gdo-qa` agent (`Agent` tool, `isolation: "worktree"`) with a
   **`## Brief`** per `.claude/conventions.md` — the ticket body verbatim
   is what it re-verifies against, so it must be complete. If the custom
   agent type isn't loaded this session, instruct it to read and follow
   `.claude/agents/gdo-qa.md` directly, same pattern as the other
   triggers.
2. Parse the outcome and act — the four outcomes aren't mutually exclusive
   with the actions below; do all that apply:

   Either way, the ticket passes through `qa` first — `merged` only
   transitions to `qa`, never directly to `in-progress` or `done` (see the
   state machine in `.claude/conventions.md`). On the **clean** path
   `finish` does that hop for you (below), so only run
   `python .claude/scripts/gdo_board.py set-status <ID> qa` + commit
   explicitly on the regression path.

   **If the ticket's own acceptance criteria are NOT MET (regression):**
   - `Edit` the ticket file to append a `## QA Regression Notes` section to
     its body (after `## Notes` if present) with the agent's
     acceptance-criteria findings verbatim — this is what a re-invoked
     implementer reads, since there's no open PR left to comment on once
     something's merged.
   - Read the ticket's current `attempts`, then
     `python .claude/scripts/gdo_board.py set-status <ID> in-progress
     --attempts <current+1>`, commit. (Same counter and cap as review
     rejections — see `CLAUDE.md`.)
   - If `attempts` reached 3: `set-status <ID> blocked` instead, commit,
     and stop — a QA regression this persistent needs a human look, not
     another automatic pass.
   - Tell the user plainly: this ticket passed review but broke on merge.
     Further re-implementation is a manual step for now — run
     `/gdo-implement <ID>` again once ready (Phase 6's orchestrator will
     chain this automatically; this skill doesn't yet).

   **For each new issue found, outside the ticket's own scope:**
   - Allocate an ID: `python .claude/scripts/gdo_board.py next-id BUG`.
   - Write `tasks/bugs/<BUG-ID>-<slug>.md` using
     `tasks/_templates/bug.md`'s shape: `epic` = the same epic as the
     ticket QA was testing, `status: backlog`, `filed_by: gdo-qa`,
     `found_in_ticket: <ID>`, and the repro/expected-vs-actual from the
     agent's report in the body, verbatim — don't paraphrase away detail
     someone will need to reproduce it.
   - Don't commit it here. On the clean path, `finish --bug <path>` (below)
     commits the bug files alongside the ticket in one call. On the
     regression path only, commit them yourself:
     `git add tasks/bugs/ && git commit -m "<BUG-ID>: filed by gdo-qa from <ID>"`.

   **If the ticket's own criteria are met and nothing else was found
   (`clean`), or once the found-but-out-of-scope issues above are filed and
   the ticket's own criteria held:**
   - `python .claude/scripts/gdo_board.py finish <ID>` — `merged` → `qa` →
     `done`, committed and pushed in one call. Pass `--bug <path>` once per
     bug file you wrote above so they land in the same commit.

3. Run `python .claude/scripts/gdo_board.py board --epic <epic>` and show
   the user the result — any new `BUG-NNN` should now appear, and be
   `ready-to-start` if the epic is still `ready`/`in-progress`.

## Ground rules

- Never set `status: done` without the agent's report actually confirming
  every acceptance criterion — a `clean` outcome is not the default; it's
  what the agent found.
- Don't drop a finding because it seems minor — file it as a bug and let a
  human triage priority; QA's job is visibility, not judgment calls about
  what's worth fixing.
- One bug ticket per distinct issue — don't bundle unrelated findings into
  one ticket just to save a file.
