---
id: BUG-001
epic: EPIC-001
title: info.py crashes with unhandled traceback on malformed/unsupported --format
status: in-progress
depends_on: []
attempts: 0
pr_url: null
owner_agent: null
created: 2026-08-23
filed_by: gdo-qa
found_in_ticket: TICKET-003
---

## Repro

From repo root, run any of:

- `python tools/smoke/info.py --format=xml`
- `python tools/smoke/info.py --format`
- `python tools/smoke/info.py foo`

**Expected:** a bad/unrecognized argument should either print a clean
usage/error message to stderr and exit non-zero, or fall back to a
sensible default — not crash.

**Actual:** all three inputs raise an unhandled Python exception with a
full traceback:
- `--format=xml` → uncaught `KeyError: 'xml'` (unrecognized value looked up
  directly in the format dict).
- `--format` (no `=value`) → uncaught `IndexError: list index out of
  range` (from `args[0].split("=", 1)[1]` when there's no `=`).
- `foo` (positional arg without `=`) → same `IndexError`.

Exit code is 1 in all three cases — incidentally "correct" as a failure
signal, but via an unhandled crash rather than intentional error handling.

## Acceptance criteria

- `python tools/smoke/info.py --format=xml` exits non-zero with a clean,
  single-line error message on stderr — no Python traceback.
- `python tools/smoke/info.py --format` (no value) and
  `python tools/smoke/info.py foo` (no `=`) both handled the same way —
  clean error, no traceback, no `IndexError`.
- The two existing acceptance criteria from TICKET-003 (no-args text
  output, `--format=json` output) still hold — this is an additive fix,
  not a rewrite.

## Notes

Found during `gdo-qa`'s post-merge exploratory pass on TICKET-003, whose
acceptance criteria deliberately scoped out any `--format` value besides
`json` — this bug is that intentionally-uncovered gap, not a regression of
anything TICKET-003 promised.
