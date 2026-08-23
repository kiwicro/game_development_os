---
name: gdo-mvp
description: Scope the MVP (first playable slice) from an approved GDD, iterating with the user, and write docs/mvp.md. Use when the user wants to define or revise MVP scope. Refuses to run until docs/gdd.md is approved.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, AskUserQuestion
---

# /gdo-mvp — MVP Scoping

Arguments passed: `$ARGUMENTS` (usually empty).

Read `CLAUDE.md` first if you haven't this session.

## Gate check (hard block)

Read `docs/gdd.md`. If it doesn't exist, or its frontmatter `status` is not
`approved`, **stop and refuse**: tell the user the GDD needs to finish
`/gdo-gdd` (including the design review) before MVP scoping can start. Don't
draft anything in this state, even as a "rough idea" — the whole point of
the gate is that MVP scope decisions should rest on a design the reviewer
has actually looked at.

If `docs/mvp.md` already exists, check its `status`:
- `draft` → resume.
- `approved` → tell the user it's already approved, ask if they want to
  revise it. If yes, treat as a real edit: set `status: draft`, and note
  that any epics already drawn from the old scope may need a look once the
  new MVP is approved (don't auto-touch `tasks/` — just flag it).

## Scoping the cut

Read the full GDD — pillars, core loop, systems, constraints. Your job here
is closer to a producer than a designer: propose what subset of the GDD
constitutes the smallest slice that proves the core loop is actually fun,
given the stated (or absent) team/timeline constraints. Concretely:

1. Draft a proposed cut: which pillars/systems are **in** for MVP, which are
   **deferred**, and why — tie every inclusion back to "does this prove the
   core loop" rather than "would this be cool to have."
2. Propose **success criteria** — how anyone will know the MVP actually
   worked. These should be testable/observable (e.g. "a player can complete
   one full loop iteration in under 90 seconds without instruction"), not
   vibes.
3. Present the proposed cut to the user. This is a negotiation, not a
   presentation — expect pushback on what's in/out, and expect the user has
   context (team capacity, a demo deadline, an investor ask) you don't. Use
   AskUserQuestion for genuine in/out calls where you want a clean decision;
   otherwise keep it conversational.
4. Iterate until the user approves the cut.

## Writing docs/mvp.md

```yaml
---
status: draft
gdd_version: <the version number from docs/gdd.md at time of writing>
---
```

Body: `## Slice Definition` (one paragraph — what the MVP actually is),
`## In Scope`, `## Out of Scope` (explicitly deferred, not just omitted —
this list is what future epics outside the MVP will draw from),
`## Success Criteria`, `## Constraints`.

On user approval, set `status: approved` and tell them `/gdo-epic` is now
unblocked.

## Ground rules

- Never set `status: approved` without the user explicitly saying to.
- `gdd_version` is a snapshot, not a live link — if the GDD changes
  materially after MVP approval, that's a judgment call for the user about
  whether MVP scope needs revisiting; flag it if you notice the GDD has a
  higher version than what mvp.md recorded, but don't block on it.
