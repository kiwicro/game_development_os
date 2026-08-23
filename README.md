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

Phase 5 — post-merge QA. Every stage of the per-ticket pipeline exists and
has been run for real against a live GitHub repo: `/gdo-implement`
(implement → PR), `/gdo-review` (review → iterate → merge, tested on both a
clean approve and a seeded reject → fix → re-review cycle), and
`/gdo-qa-run` (re-verify on mainline → file bug tickets for anything found
outside a ticket's own scope → done). Only `/gdo-run` — the orchestrator
that chains all three automatically across an epic's whole ticket queue
without a human triggering each stage — doesn't exist yet. Promoting an
epic to `ready` today queues it for that.

`/gdo-gdd`, `/gdo-mvp`, `/gdo-epic`, `/gdo-board`, the `gdo-design-reviewer`
agent, and `.claude/scripts/gdo_board.py` (the deterministic reader/writer
for `tasks/` state) round out the human-in-the-loop and bookkeeping side.

Requires Python 3.8+ on PATH for the board tooling — independent of
whatever engine/language the game itself uses.
