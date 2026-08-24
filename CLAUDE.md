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
  skills/       # /gdo-setup, /gdo-gdd, /gdo-mvp, /gdo-epic, /gdo-board,
                # /gdo-implement, /gdo-review, /gdo-qa-run, /gdo-run
  agents/       # custom subagent types: design-reviewer, orchestrator,
                # implementer, reviewer, qa, artist
  scripts/      # gdo_board.py, gdo_placeholder_art.py
docs/
  gdd.md        # Game Design Document
  mvp.md        # MVP scope cut
  engine.md     # detected engine + any connected MCP, written by /gdo-setup
tasks/
  epics/        # EPIC-NNN-<slug>.md
  tickets/      # TICKET-NNN-<slug>.md
  bugs/         # BUG-NNN-<slug>.md  (filed by QA, same schema as tickets)
  art/          # ART-NNN-<slug>.md  (art work, same schema as tickets)
```

Setting this framework up on an actual game project (as opposed to working
inside this repo, which is the framework's own home) is `/gdo-setup`'s job
— see that skill for installing the framework into a target project and
connecting it (git/GitHub, engine detection, optional engine-MCP guidance).

## Ticket conventions — see `.claude/conventions.md`

IDs and filenames, the ticket frontmatter schema, the status machine, branch/PR
conventions, and the ground rules for agents all live in
`.claude/conventions.md`. They were moved there (not copied) so a sub-agent can
read the ~100 lines it actually needs instead of this whole file.

Everything below is the orchestration context around a ticket, which the
orchestrator and any human working in `tasks/` still need.

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

**Workflow commands.** Each of these wraps a multi-step git+status sequence
that used to be spelled out call-by-call in the skills. Prefer them over
hand-rolling the same steps — they cut a ticket's bookkeeping from ~20 tool
calls to ~5, and more importantly they make the *ordering* unskippable:

```
python .claude/scripts/gdo_board.py start  <ID> [--owner NAME] [--no-commit]
python .claude/scripts/gdo_board.py opened <ID> --pr-url URL
python .claude/scripts/gdo_board.py land   <ID> [--pr-url URL] [--no-push]
python .claude/scripts/gdo_board.py qa-queue [--epic EPIC-NNN] [--json]
python .claude/scripts/gdo_board.py finish <ID> [<ID> ...] [--bug PATH ...]
python .claude/scripts/gdo_board.py parallel-batch [--epic EPIC-NNN] [--max N]
python .claude/scripts/gdo_board.py doctor [--epic EPIC-NNN] [--fix]
```

- `start` — `backlog`/`ready` → `in-progress`, **committed**. Call this
  immediately before spawning an implementer.
- `opened` — → `in-review`, recording `pr_url`, committed.
- `land` — guards the branch against `tasks/**` edits, squash-merges,
  `pull --rebase`s, sets `merged`, commits, pushes. Refuses to merge a
  branch that modifies board state, naming the offending files.
- `qa-queue` — everything sitting at `merged`, i.e. landed but not yet
  verified. QA batches over this rather than running once per ticket.
- `finish` — `merged` → `qa` → `done` for **one or more** IDs, committing
  any bug files QA filed alongside, in one commit and one push. Clean-QA
  path only; a regression reopens that ticket instead.
- `parallel-batch` — ready items with no dependency on each other and no
  overlapping declared `touches:`, i.e. safe to hand to several implementers
  at once. It reports which items declared no `touches:` and therefore
  couldn't be checked — the caller has to judge those from the ticket
  bodies.
- `doctor` — reconciles frontmatter against real git/gh state and reports
  anything that drifted. Run it at the start of any resumed run. `--fix`
  resets the one unambiguous case: `in-progress` with no branch and no PR,
  i.e. a session that died between `start` and dispatch.

All of them validate and fail loudly *before* mutating anything, so a failed
call leaves `tasks/` exactly as it found it.

`board`'s text output leads with a `NEEDS ATTENTION` section (anything
`blocked`, plus anything at `attempts: 2` — one rejection or regression
from blocking) before the per-epic detail, so what actually needs a human
is visible without scanning every ticket; `--json` carries the same thing
as a top-level `needs_attention` map. Both are computed, not stored — don't
expect to find a `needs_attention` field in any `tasks/*.md` file.

`set-status` validates the transition against the state machine in
`.claude/conventions.md` and
refuses illegal ones unless `--force` is passed. It only ever rewrites the
specific frontmatter fields it's told to change — body text and every other
field are left byte-identical. Run `validate` after any batch of manual
`tasks/` edits (e.g. right after `/gdo-epic` writes a new epic's tickets).

Two hazards these commands exist to remove — worth knowing about, because
anything that bypasses `start`/`land` walks straight back into them:

**Commit status transitions before spawning a worktree-isolated agent.**
`Agent` calls with `isolation: "worktree"` fork from the repo's committed
git state, not from uncommitted changes sitting in the main working tree —
confirmed the hard way in Phase 3: a `set-status ... in-progress` call left
uncommitted locally, then a worktree agent spawned right after, saw the
ticket as still `backlog`. `start` commits for you, which is the point.

**Pull before pushing a board-state commit right after a merge.** `gh pr
merge` advances `origin/main` on GitHub independently of the local
checkout. Committing a ticket's `merged` status locally and pushing right
after, without a `git pull --rebase origin main` in between, gets rejected
as non-fast-forward. `land` does the rebase-pull in the right place.

**Only this script writes board state.** An implementer that commits a
`tasks/` change on its own branch collides with the orchestrator's status
commit and breaks the squash-merge — this happened in Phase 4 (BUG-002).
`land`'s guard now rejects such a branch before merging rather than leaving
it to be discovered as a conflict.

## Art pipeline

Art needs are `ART-NNN` tickets (`tasks/art/`), implemented by
`gdo-artist` instead of `gdo-implementer`, through the same
implement → PR → review → merge → QA cycle as any code ticket. A code
ticket that needs an asset first should `depends_on` the `ART-NNN` ticket
for it, same mechanism as any other dependency.

**Default is placeholder, always, autonomously.** `gdo-artist` doesn't
search the project's existing assets, doesn't pull third-party art, and
doesn't call out to any external generation service — it generates
original, trivial placeholder art via `.claude/scripts/gdo_placeholder_art.py`
(stdlib-only PNG/WAV writer, no PIL dependency): a "missing texture"
checkerboard or solid color for 2D images, a silent stub for audio. This is
a deliberate choice, not a limitation to route around: placeholders carry
zero licensing risk and never block the pipeline, matching how real studios
actually handle early production (grey-box first). Placeholder files are
named with `.placeholder.` in the filename (e.g.
`player_idle.placeholder.png`) so they're easy to find and swap for real
art later — `gdo-reviewer` checks for this and for the PR being honest
about what it shipped.

3D models and anything else the generator can't meaningfully fake aren't
routed around with a fake file — `gdo-artist` escalates those the same way
any agent escalates a can't-proceed-without-a-decision case.

If a project's `docs/engine.md` (written by `/gdo-setup`) records a
connected engine MCP, that's available for `gdo-artist` (or any agent) to
use where it's naturally the right tool — this framework doesn't hard-wire
any engine-specific tool calls anywhere, agents just use whatever's
actually in their session.

