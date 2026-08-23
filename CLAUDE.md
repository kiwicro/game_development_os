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
attempts: 0              # rework count: incremented by a review rejection
                          # OR a QA regression, same counter, cap 3 either way
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
backlog → ready → in-progress → in-review ─┬─→ merged → qa ─┬─→ done
                        ^                   │                │
                        │                   └── changes-requested (attempts++, cap 3)
                        └───────────────────────────────────┘
                          (qa found the merged change itself doesn't meet
                           acceptance criteria — reopens for another pass;
                           an unrelated bug QA finds becomes a new BUG-NNN
                           instead of reopening this ticket)
```

`attempts` is one counter shared by both rework paths above — a review
rejection and a QA regression both increment it, both share the same cap
of 3. At 3, the ticket goes to `blocked` instead of reopening again; a
human needs to look at it.

**Rework feedback has to be durable, not just conversational**, since the
agent that re-does the work may be a fresh spawn with no memory of why it's
being re-invoked:
- Review rejections: `gdo-reviewer` posts its findings as a real PR
  comment (`gh pr comment`), not just in its returned report. A re-invoked
  implementer reads `gh pr view <pr> --comments` if the feedback isn't
  already in its prompt.
- QA regressions: there's no open PR left once something's merged, so
  whatever reopens the ticket appends a `## QA Regression Notes` section to
  the ticket file's own body instead.

`blocked` is a side state, enterable from any status, for two reasons only:
(1) `depends_on` includes a ticket that isn't `done`, or (2) `attempts`
exhausted its cap without approval. A `blocked`-on-exhausted-attempts ticket
is what triggers the orchestrator's escalation to the user — it does not
retry silently past the cap. `blocked` exits to `backlog` (re-triage) or
`in-progress` (a human resolved the block and work resumes directly).

This machine is enforced in code, not just here — see the next section.

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

## The board helper — .claude/scripts/gdo_board.py

Stdlib-only Python, no dependencies to install. This is the authoritative
reader/writer for `tasks/` state — skills and agents should shell out to it
rather than hand-parsing or hand-editing frontmatter, so "what's ready,"
"what's blocked and why," and "is this status transition even legal" are
answered the same way everywhere instead of by each agent's own reading of
the schema.

```
python .claude/scripts/gdo_board.py board [--epic EPIC-NNN] [--json]
python .claude/scripts/gdo_board.py ready --epic EPIC-NNN [--json]
python .claude/scripts/gdo_board.py next-id EPIC|TICKET|BUG
python .claude/scripts/gdo_board.py set-status <ID> <new-status>
    [--pr-url URL] [--attempts N] [--owner NAME] [--force]
python .claude/scripts/gdo_board.py cycles
python .claude/scripts/gdo_board.py validate
```

`board`'s text output leads with a `NEEDS ATTENTION` section (anything
`blocked`, plus anything at `attempts: 2` — one rejection or regression
from blocking) before the per-epic detail, so what actually needs a human
is visible without scanning every ticket; `--json` carries the same thing
as a top-level `needs_attention` map. Both are computed, not stored — don't
expect to find a `needs_attention` field in any `tasks/*.md` file.

`set-status` validates the transition against the state machine above and
refuses illegal ones unless `--force` is passed. It only ever rewrites the
specific frontmatter fields it's told to change — body text and every other
field are left byte-identical. Run `validate` after any batch of manual
`tasks/` edits (e.g. right after `/gdo-epic` writes a new epic's tickets).

**Commit status transitions before spawning a worktree-isolated agent.**
`Agent` calls with `isolation: "worktree"` fork from the repo's committed
git state, not from uncommitted changes sitting in the main working tree —
confirmed the hard way in Phase 3: a `set-status ... in-progress` call left
uncommitted locally, then a worktree agent spawned right after, saw the
ticket as still `backlog`. It didn't matter for the implementer (it doesn't
read status), but anything that *does* depend on the ticket's status being
current inside a spawned worktree needs that status change committed (a
plain local commit is enough — it doesn't need to be pushed) before the
`Agent` call, not just written to disk.

**Pull before pushing a board-state commit right after a merge.** Found in
Phase 4: `gh pr merge` advances `origin/main` on GitHub independently of
the local checkout. Committing a ticket's `merged` status locally and
pushing right after, without a `git pull --rebase origin main` in between,
gets rejected as non-fast-forward.

## Branch and PR conventions

- Branch: `ticket/TICKET-NNN-<slug>` (matches the ticket filename slug).
- Commit messages: reference the ticket ID, e.g. `TICKET-014: add
  drag-and-drop handlers to inventory slots`.
- PRs: title mirrors the ticket title, body links back to the ticket file
  path (not just the ID — the file is the spec) and lists the acceptance
  criteria as a checklist.
- Merge strategy: squash merge, delete branch after merge.

## Ground rules for agents operating in this repo

- Use `.claude/scripts/gdo_board.py` to read computed state (ready/blocked/
  cycles) and to change `status`/`pr_url`/`attempts`/`owner_agent`. Direct
  edits to those fields via `Edit`/`Write` are how the script's own
  validation gets bypassed by accident.
- Never flip a ticket or epic to `ready` yourself — that's a human decision.
- Never hand-wave acceptance criteria as met; the reviewer and QA agent
  check the actual running behavior, not just that code was written.
- If a ticket's acceptance criteria are ambiguous or contradict the GDD/MVP,
  stop and flag it (`status: blocked`, note why) rather than guessing.
- This framework is engine-agnostic by design — don't assume Unity/Godot/
  Unreal specifics unless a ticket says so explicitly.
