# Game Development OS

An engine-agnostic Claude Code orchestration framework for running a game's
production pipeline end-to-end.

- **You drive the top of the funnel**: `/gdo-gdd`, `/gdo-mvp`, and
  `/gdo-epic` walk you through writing the Game Design Document, scoping the
  MVP, and breaking approved scope into epics and tickets. A GDD draft must
  pass a critique from the `gdo-design-reviewer` agent — a skeptical,
  independent game-designer persona — before it can be approved and MVP
  scoping unlocks.
- **The framework drives execution**: once you promote an epic to `ready`,
  `/gdo-run` works through its tickets autonomously — implement, open a real
  GitHub PR, review, iterate on feedback, merge, QA-test — looping until the
  epic is done. It only comes back to you when the epic finishes, a ticket
  fails repeatedly, or a decision needs your judgment.

See `CLAUDE.md` for the ticket/epic schema, status machine, and conventions
the skills and agents rely on. Being built in phases — see the project's
plan for current status.

## Status

Phase 6 — full autonomy. `/gdo-run` chains implement → review/iterate →
merge → QA automatically across an epic's entire ticket queue via
`gdo-orchestrator`, resuming each ticket at whatever stage it's actually
at. Verified for real: spawned as a single background agent against
EPIC-001 with a mix of stalled and fresh work (two tickets sitting merged
but un-QA'd, one bug ticket needing the full cycle from scratch), it ran
completely unattended — no manual steps between invocation and the epic
reaching `done` — including recovering from its own operational hiccup
(stale worktree references blocking a branch delete) without escalating.
Independently re-verified afterward: git history, GitHub PR state, and the
actual shipped fix all matched its report exactly.

The single-ticket triggers (`/gdo-implement`, `/gdo-review`,
`/gdo-qa-run`) still exist and work standalone — useful for handling one
ticket by hand without invoking full epic autonomy. `/gdo-gdd`,
`/gdo-mvp`, `/gdo-epic`, `/gdo-board`, the `gdo-design-reviewer` agent, and
`.claude/scripts/gdo_board.py` round out the human-in-the-loop and
bookkeeping side.

Remaining framework work is polish, not new capability: an observability
pass (a clearer status view / dashboard) and hardening from one more full
run.

Requires Python 3.8+ on PATH for the board tooling — independent of
whatever engine/language the game itself uses.
