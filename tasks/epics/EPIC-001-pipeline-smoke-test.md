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

A single tiny script whose only job is to prove a ticket can go from
`backlog` to a real, verifiable, merged change through this pipeline.
Nothing else — no game logic belongs here.

## Tickets

- TICKET-001 — Add pipeline smoke-test script

## Done when

TICKET-001 is `done`. This epic can gain more tickets later if a phase
needs a new kind of fixture to test against (e.g. Phase 4 wants a
deliberately-broken ticket to prove the review-reject path).
