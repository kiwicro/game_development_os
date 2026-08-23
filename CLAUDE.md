# Game Development OS

An engine-agnostic Claude Code orchestration framework for running a game's
production pipeline end-to-end: game design → MVP scoping → epic/ticket
breakdown (human-in-the-loop) → autonomous implementation → PR review → QA
(fully autonomous, per approved epic).

See `docs/gdd.md` and `docs/mvp.md` for the current project's design and
scope once they exist. This file documents the conventions the skills and
agents in `.claude/` rely on — read it before touching `tasks/`.

## Directory layout

```
.claude/
  skills/       # /gdo-gdd, /gdo-mvp, /gdo-epic, /gdo-board, /gdo-run
  agents/       # custom subagent types: design-reviewer, orchestrator, implementer, reviewer, qa
docs/
  gdd.md        # Game Design Document
  mvp.md        # MVP scope cut
tasks/
  epics/        # EPIC-NNN-<slug>.md
  tickets/      # TICKET-NNN-<slug>.md
  bugs/         # BUG-NNN-<slug>.md  (tickets filed by QA, same schema as tickets)
```

## IDs and filenames

`EPIC-NNN`, `TICKET-NNN`, `BUG-NNN` — zero-padded 3-digit, monotonically
increasing per prefix across the whole `tasks/` tree (don't reuse numbers,
even across subfolders). Filename is `<ID>-<kebab-slug>.md`, e.g.
`TICKET-014-inventory-drag-drop.md`. The ID inside the frontmatter is the
source of truth if filename and frontmatter ever disagree.

## Ticket frontmatter schema

Every file in `tasks/tickets/` and `tasks/bugs/` starts with YAML
frontmatter:

```yaml
---
id: TICKET-014
epic: EPIC-002
title: Inventory drag-and-drop
status: backlog
depends_on: []          # list of ticket IDs that must be `done` first
attempts: 0              # implementer attempts on the current review cycle
pr_url: null
owner_agent: null        # set by the orchestrator while a ticket is active
created: 2026-08-23
---
```

Body (markdown, free-form but keep these sections):

```markdown
## Context
One or two sentences linking back to the GDD/MVP section this implements.

## Acceptance criteria
- Observable, testable behavior. Not implementation detail.
- One bullet per criterion; the reviewer and QA agent check against these directly.

## Notes
Anything else: design constraints, explicitly out of scope, links.
```

Epics (`tasks/epics/`) use the same frontmatter shape minus `depends_on`/
`attempts`/`pr_url`/`owner_agent`, plus `status: draft | ready | in-progress
| done`. An epic's body is the pitch/scope summary; its tickets are the unit
of execution.

## Status machine (tickets/bugs)

```
backlog → ready → in-progress → in-review ─┬─→ merged → qa → done
                        ^                   │
                        └── changes-requested (attempts++, cap 3)
```

`blocked` is a side state, entered from any status, for two reasons only:
(1) `depends_on` includes a ticket that isn't `done`, or (2) `attempts`
exhausted its cap without approval. A `blocked`-on-exhausted-attempts ticket
is what triggers the orchestrator's escalation to the user — it does not
retry silently past the cap.

Epics move `draft → ready` only when the user explicitly approves them
(`/gdo-epic` does this on request, never automatically). `ready` is the
signal `/gdo-run` treats as "safe to execute autonomously." Nothing in
`tasks/` should be hand-edited into `ready` without that conversation
having happened.

## Design doc gate (docs/gdd.md, docs/mvp.md)

`docs/gdd.md` frontmatter: `status: draft | in-review | approved`,
`version` (int, bumped on substantive revision), `last_reviewed` (date or
`null`). It also carries a `## Review Log` section — one entry per design
review round, each recording the round number, date, verdict, condensed
findings, and resolution.

`docs/mvp.md` frontmatter: `status: draft | approved`, `gdd_version` (a
snapshot of the GDD version it was scoped against).

The pipeline gates hard, front to back: `/gdo-mvp` refuses to run unless
`docs/gdd.md` is `approved`; `/gdo-epic` refuses to run unless
`docs/mvp.md` is `approved`. A GDD reaches `approved` only after at least
one pass through the `gdo-design-reviewer` agent (spawned automatically by
`/gdo-gdd`) and an explicit user decision — the reviewer's verdict informs
that decision, it never sets status by itself. Editing an already-approved
`docs/gdd.md` resets it to `draft` and re-requires the gate.

## Branch and PR conventions

- Branch: `ticket/TICKET-NNN-<slug>` (matches the ticket filename slug).
- Commit messages: reference the ticket ID, e.g. `TICKET-014: add
  drag-and-drop handlers to inventory slots`.
- PRs: title mirrors the ticket title, body links back to the ticket file
  path (not just the ID — the file is the spec) and lists the acceptance
  criteria as a checklist.
- Merge strategy: squash merge, delete branch after merge.

## Ground rules for agents operating in this repo

- Never flip a ticket or epic to `ready` yourself — that's a human decision.
- Never hand-wave acceptance criteria as met; the reviewer and QA agent
  check the actual running behavior, not just that code was written.
- If a ticket's acceptance criteria are ambiguous or contradict the GDD/MVP,
  stop and flag it (`status: blocked`, note why) rather than guessing.
- This framework is engine-agnostic by design — don't assume Unity/Godot/
  Unreal specifics unless a ticket says so explicitly.
