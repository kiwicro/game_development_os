---
name: gdo-epic
description: Break an approved MVP (or a specific area of it) into epics and tickets under tasks/, iterating with the user, then promote an epic to ready when they explicitly approve it for autonomous execution. Refuses to run until docs/mvp.md is approved.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, AskUserQuestion, Bash(python .claude/scripts/gdo_board.py:*)
---

# /gdo-epic — Epic & Ticket Breakdown

Arguments passed: `$ARGUMENTS` — optionally names a specific area of the MVP
to break down first (e.g. "inventory system"). If empty, ask the user what
to tackle, or propose an order based on dependencies you can see in the MVP
doc (e.g. core loop before peripheral systems).

Read `CLAUDE.md` first if you haven't this session — the ticket/epic
frontmatter schema and status machine below assumes it.

## Gate check (hard block)

Read `docs/mvp.md`. If it doesn't exist or `status` isn't `approved`, stop
and refuse: tell the user to finish `/gdo-mvp` first.

## Allocating IDs

IDs are monotonically increasing per prefix (`EPIC-`, `TICKET-`, `BUG-`)
across the whole `tasks/` tree — never reused, even if a file is later
deleted. Don't compute this by eye; shell out to the board helper, which is
the authoritative source for it:

```
python .claude/scripts/gdo_board.py next-id EPIC
python .claude/scripts/gdo_board.py next-id TICKET
```

Call it once per file you're about to create, right before writing that
file (not all up front) — if you're writing several tickets in one pass,
each `next-id` call reflects the files written so far.

## Breaking down scope

Work from `docs/mvp.md`'s in-scope list (or the user-specified area). For
the area under discussion:

1. Propose one or more **epics** — cohesive chunks of the MVP scope, each
   independently meaningful (not "part 1 of inventory" / "part 2 of
   inventory" split arbitrarily).
2. For each epic, propose **tickets** — scoped to roughly a day to a week of
   work each, per `CLAUDE.md`. Each ticket needs acceptance criteria that
   are actually checkable by running the game or reading a diff (this is
   what the reviewer and QA subagents will check against later, once
   autonomous execution exists) — not "code is clean" or "works well."
   Surface dependencies between tickets explicitly (`depends_on`).
3. Present the proposed breakdown to the user — epic summaries first, then
   ticket lists per epic. This is genuinely collaborative: the user may
   want tickets split differently, scoped differently, reordered, or cut
   entirely. Iterate until they're satisfied. Use AskUserQuestion for
   clean-cut decisions (e.g. "split this into two tickets or keep it as
   one?"), plain conversation otherwise.

## Writing files

Use `tasks/_templates/epic.md` and `tasks/_templates/ticket.md` as the
shape. Epics start `status: draft`. Tickets start `status: backlog`
(regardless of their epic's status — a ticket only becomes eligible to run
once its epic is `ready` *and* its own `depends_on` are satisfied, per
`CLAUDE.md`'s status machine).

Write the epic file first (so you know its ID for the tickets' `epic:`
field), then each ticket file. Update the epic's `## Tickets` list with the
final ticket IDs once all are written.

## After writing

Run `python .claude/scripts/gdo_board.py validate` once you've written the
epic and its tickets. It catches mistakes like a `depends_on` typo pointing
at a nonexistent ticket, or an accidental dependency cycle, before they sit
undetected in the repo. Fix anything it flags before moving on.

## Promoting an epic to ready

An epic sitting at `status: draft` does nothing — it's inert until promoted.
Once the user is happy with an epic and its tickets, ask explicitly: *"Set
EPIC-NNN to ready? This releases it to autonomous execution once /gdo-run
exists."* Only flip `status: ready` on an explicit yes. Never do this as
part of routine drafting, and never do it for an epic the user hasn't
reviewed in this session.

(Autonomous execution itself — `/gdo-run` — doesn't exist yet as of this
skill; promoting to `ready` today just marks the epic as design-approved and
queued for when it does.)

## Ground rules

- Never invent acceptance criteria the user hasn't at least implicitly
  agreed to — read back what you're about to write if there's any doubt
  they'd recognize it.
- Don't let scope creep into a ticket beyond what its title implies; split
  instead.
- If a proposed ticket's dependencies would create a cycle, say so and
  resolve it with the user before writing anything.
