---
id: TICKET-003
epic: EPIC-001
title: Add pipeline info script with --format flag
status: in-progress
depends_on: []
attempts: 0
pr_url: null
owner_agent: null
created: 2026-08-23
---

## Context

Third smoke-test ticket under EPIC-001 (see that epic — infrastructure
only, not game content). This one exercises `gdo-qa`: its acceptance
criteria only specify two invocations, narrowly enough that a correct
implementation of exactly what's asked can still pass review while leaving
an unsupported-input path untested — which is what the post-merge QA pass
exists to catch.

## Acceptance criteria

- A script exists at `tools/smoke/info.py`.
- Running `python tools/smoke/info.py` (no arguments) prints exactly
  `Game Development OS pipeline: v1 (text)` and exits 0.
- Running `python tools/smoke/info.py --format=json` prints exactly
  `{"pipeline": "Game Development OS", "version": "v1"}` and exits 0.
- The script has a one-line docstring or comment stating it's a pipeline
  smoke test, not game logic.

## Notes

Only the two invocations above are in scope for this ticket's acceptance
criteria — deliberately. What happens with any other `--format` value is
unspecified here on purpose.
