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

Phase 2 — task board. `/gdo-gdd`, `/gdo-mvp`, `/gdo-epic`, `/gdo-board`, the
`gdo-design-reviewer` agent, and `.claude/scripts/gdo_board.py` (the
deterministic reader/writer for `tasks/` state — ready/blocked computation,
status-transition validation, ID allocation, cycle detection) are
implemented. Autonomous execution (`/gdo-run` and the implementer/reviewer/
QA agents) doesn't exist yet — promoting an epic to `ready` today just marks
it queued for later.

Requires Python 3.8+ on PATH for the board tooling — independent of
whatever engine/language the game itself uses.
