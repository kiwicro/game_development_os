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

Phase 7 — observability. The full pipeline works end to end and has been
run for real (see below); this phase sharpened how it's monitored.
`/gdo-board` now leads with a `NEEDS ATTENTION` section — anything
`blocked`, plus anything one rejection or regression away from blocking —
before the per-epic detail, so what needs a human is visible at a glance
rather than found by reading every ticket. `gdo-orchestrator`'s final
report follows a fixed template (status first, then a summary, a tickets
table, blocked items, bugs filed) instead of free-form prose, so `/gdo-run`
relays a consistent shape every time.

`/gdo-run` chains implement → review/iterate → merge → QA automatically
across an epic's entire ticket queue via `gdo-orchestrator`, resuming each
ticket at whatever stage it's actually at. Verified for real: spawned as a
single background agent against EPIC-001 with a mix of stalled and fresh
work, it ran completely unattended to a finished epic, including
recovering from its own operational hiccup without escalating.
Independently re-verified afterward — git history, GitHub PR state, and
the actual shipped fix all matched its report exactly.

The single-ticket triggers (`/gdo-implement`, `/gdo-review`,
`/gdo-qa-run`) still exist and work standalone — useful for handling one
ticket by hand without invoking full epic autonomy. `/gdo-gdd`,
`/gdo-mvp`, `/gdo-epic`, the `gdo-design-reviewer` agent, and
`.claude/scripts/gdo_board.py` round out the human-in-the-loop and
bookkeeping side.

Remaining framework work (Phase 8) is hardening, not new capability: one
more full run to shake out rough edges.

Requires Python 3.8+ on PATH for the board tooling — independent of
whatever engine/language the game itself uses.
