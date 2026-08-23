---
id: EPIC-001
title: Pipeline Smoke Test
status: ready
created: 2026-08-23
---

## Goal

Infrastructure-only epic, **not game content**. Exists to validate the
gdo-implementer / gdo-reviewer / gdo-qa / orchestrator pipeline end-to-end
as each phase of the framework gets built, using a trivial, low-stakes
change instead of inventing placeholder game design. Real game epics start
once `/gdo-gdd` → `/gdo-mvp` → `/gdo-epic` has been run for an actual game
concept — this epic deliberately doesn't touch `docs/gdd.md` or
`docs/mvp.md` and isn't subject to their gates.

## Scope

Tiny scripts whose only job is to prove a ticket can go from `backlog` to a
real, verifiable, merged change through this pipeline. Nothing else — no
game logic belongs here.

## Tickets

- TICKET-001 — Add pipeline smoke-test script
- TICKET-002 — Add pipeline version-check script (seeded wrong on purpose
  once, to prove the reviewer's reject → fix → re-review loop actually
  works, not just the happy path)

## Done when

TICKET-001 and TICKET-002 are `done`. This epic can gain more tickets later
if a phase needs a new kind of fixture to test against (e.g. Phase 5 wants
one QA can find a real bug in).
