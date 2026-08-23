---
id: TICKET-001
epic: EPIC-001
title: Add pipeline smoke-test script
status: backlog
depends_on: []
attempts: 0
pr_url: null
owner_agent: null
created: 2026-08-23
---

## Context

Validates that the `gdo-implementer` agent can take a ticket from backlog
to a real, verified GitHub PR. Not game content — see EPIC-001.

## Acceptance criteria

- A script exists at `tools/smoke/hello.py`.
- Running `python tools/smoke/hello.py` prints exactly
  `Game Development OS pipeline: OK` (one line, nothing else) and exits 0.
- The script has a one-line docstring or comment stating it's a pipeline
  smoke test, not game logic, so nobody mistakes it for real content later.

## Notes

Deliberately trivial — the point is to exercise implement → PR mechanics,
not to write anything clever. Keep it to a single small file.
