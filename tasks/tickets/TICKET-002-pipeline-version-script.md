---
id: TICKET-002
epic: EPIC-001
title: Add pipeline version-check script
status: in-review
depends_on: []
attempts: 0
pr_url: https://github.com/kiwicro/game_development_os/pull/2
owner_agent: null
created: 2026-08-23
---

## Context

Second smoke-test ticket under EPIC-001 — see that epic for why this exists
(infrastructure only, not game content). This one specifically exercises
the `gdo-reviewer` reject → fix → re-review loop, so its acceptance
criteria are exact enough that a subtly wrong first attempt is genuinely
wrong, not a matter of interpretation.

## Acceptance criteria

- A script exists at `tools/smoke/version_check.py`.
- Running `python tools/smoke/version_check.py` prints exactly
  `Game Development OS pipeline: v1` (one line, nothing else — no extra
  debug output, no trailing punctuation beyond the line itself) and exits 0.
- The script has a one-line docstring or comment stating it's a pipeline
  smoke test, not game logic.

## Notes

Deliberately trivial, same spirit as TICKET-001.
