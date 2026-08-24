# Roadmap — pipeline performance & robustness

Derived from the first full end-to-end run (GDD → EPIC-001, 10 items).
Observed shape: the git/PR/QA machinery structurally outweighed the coding
step per ticket. ~20 orchestrator tool calls per ticket touch no code, and
each of the 3 sub-agent spawns re-discovers context the orchestrator
already had.

Phases are ordered by dependency, not just priority. **A must land before
B and C** — the script subcommands and the brief format are what make the
spawn-reduction and parallelism changes safe.

---

## Phase A — Foundations (no behavior change, pure call reduction)  ✅ DONE

Landed on `perf/phase-a-foundations`. Verified by
`.claude/scripts/tests/test_workflow.sh` (34 cases, no network) plus
`gdo_board.py validate`.

### A1. Collapse the git+status dances into `gdo_board.py` subcommands
- [x] `start <ID>` — `backlog→ready→in-progress` (chained), then
      `git add tasks/ && git commit -m "<ID>: mark in-progress"`.
      Add `--no-commit` for callers that batch.
- [x] `opened <ID> --pr-url URL` — `→in-review` + commit.
- [x] `land <ID>` — the full merge dance, in the one correct order:
      1. **Guard:** `git diff --name-only origin/main...ticket/<ID>-<slug> -- tasks/`
         must be empty. If not, exit non-zero listing the offending files —
         this is the BUG-002 collision class, caught *before* the merge.
      2. `gh pr merge <pr_url> --squash --delete-branch`
      3. `git pull --rebase origin main`
      4. `set-status <ID> merged` + commit + push
- [x] `finish <ID> [--bug <file>...]` — `merged→qa→done`, file any bug
      files, commit, push.
- [x] Every subcommand fails loudly and leaves state unchanged on error —
      no half-applied transitions.

**Verify:** run each against a scratch repo; `gdo_board.py validate` clean
afterward. **Payoff:** ~20 bookkeeping calls/ticket → ~5, and the merge
ordering becomes impossible to get wrong.

### A2. `gdo_board.py doctor` — reconcile frontmatter against git/gh reality
- [x] For every item not `done`/`blocked`: does `ticket/<ID>-*` exist on
      origin? Is there a PR? Does its state match the frontmatter?
- [x] Report drift as a table.
- [x] `--fix`: reset `in-progress`-with-no-branch-and-no-PR back to `ready`.
- [x] Call it at the top of `/gdo-run` on resume.

**Replaces:** the manual `git branch` / `git log` audit after each of the
two session-limit deaths.

### A3. Split `.claude/conventions.md` out of `CLAUDE.md`
- [x] Extract only what sub-agents need: IDs/filenames, ticket frontmatter
      schema, status machine, branch/PR conventions, ground rules (~60 lines).
- [x] `CLAUDE.md` keeps everything and links to it — orchestrator still
      reads the full file.

### A4. Agents accept a brief instead of re-reading everything
- [x] Define the `## Brief` block: ticket body verbatim, branch name, PR
      URL, conventions, `docs/engine.md` contents.
- [x] In `gdo-implementer.md`, `gdo-artist.md`, `gdo-reviewer.md`,
      `gdo-qa.md`: change "read `CLAUDE.md` in full" to — *if your prompt
      has a `## Brief`, it already carries this; don't re-read. Otherwise
      read `.claude/conventions.md`.*
- [x] Keep the fallback path working for manual/ad-hoc spawns.

**Payoff:** ~5 rediscovery calls × 3 spawns × N tickets.

### A5. Rewire callers
- [x] `gdo-orchestrator.md` — use A1 subcommands, emit A4 briefs.
- [x] `/gdo-implement`, `/gdo-review`, `/gdo-qa-run` — same, so the manual
      path and the autonomous path stay identical.
- [x] Update each skill's `allowed-tools` for the new subcommands.

### A6. `/gdo-setup` preflight — catch the two hard blockers
- [x] Repo has ≥1 commit (`git rev-parse HEAD`).
- [x] Remote has at least one branch (`git ls-remote --heads origin`).
- [x] Local HEAD is actually pushed (no unpushed ahead-count).
- [x] Offer to fix each in place rather than just reporting.

---

## Phase B — Fewer spawns per ticket  ✅ DONE

Landed on `perf/phase-a-foundations` alongside Phase A. Verified by
`.claude/scripts/tests/test_workflow.sh` (46 cases, no network).

### B1. Conditional QA
- [x] `land` computes, **before merging**, how many commits landed on the
      base since the branch diverged, and prints a `qa-scope:` verdict:
      `trivial` (nothing landed — the merged tree is what the reviewer
      already verified), `NON-TRIVIAL` (N commits landed — QA this one
      individually), or `UNKNOWN`.
- [x] `gdo-qa` honours a per-ticket `scope` of `full` or `exploratory-only`,
      and must say so in its report rather than listing criteria it didn't
      run.
- [x] Unknown/missing scope degrades to `full`, so losing the signal (a
      session death, a different session's merge) costs time, never
      correctness.

### B2. Batched per-epic QA
- [x] `gdo_board.py qa-queue [--epic E] [--json]` — everything at `merged`.
- [x] `finish` takes **multiple IDs**: N tickets → one commit, one push.
      Validates the whole batch before mutating any of it, so a bad ID
      doesn't leave half the batch transitioned.
- [x] Orchestrator drains the queue at 3 items or when nothing else is
      implementable, whichever comes first — and **must** drain it before
      the epic can go `done`.
- [x] `NON-TRIVIAL` merges still get their own immediate pass.
- [x] `/gdo-qa-run` accepts a ticket ID, an epic ID, or nothing (drain all).

### B3. Model per agent
- [x] `gdo-artist` → `model: haiku`. Its default path is calling
      `gdo_placeholder_art.py` with dimensions the ticket already states —
      mechanical work that doesn't need a large model.
- [x] Left opus on `gdo-design-reviewer` and `gdo-implementer`; measure
      before touching the rest.

### B4. Housekeeping
- [x] One `gh pr view <n> --json ...` instead of several round-trips, in
      both `gdo-reviewer` and `gdo-implementer`.
- [x] `git worktree prune` in the orchestrator's *Finishing up*, with a note
      that directories which won't delete are inert once git has
      deregistered them.
- [ ] ~~Reusable review worktree~~ — **dropped, not implementable here.**
      Worktrees are created by the `Agent` tool's `isolation: "worktree"`,
      not by this framework, so nothing in `.claude/` can make one be
      reused across spawns. Revisit only if the harness exposes control
      over it.

## Phase C — Parallelism  ✅ DONE

### C1. Independence check
- [x] `gdo_board.py parallel-batch [--epic E] [--max N] [--json]`.
- [x] Optional `touches:` frontmatter — path globs an item expects to
      modify. Two candidates whose declared footprints intersect go into
      different waves.
- [x] Items that declare no `touches:` are reported as **not mechanically
      checked**, so the caller knows to judge them from the ticket bodies
      rather than assuming they were cleared.
- [x] `/gdo-epic` asks for `touches:` when writing tickets, and says
      plainly that omitting it costs parallelism, not correctness.
- [x] Correction worth recording: the plan said to check "no shared
      `depends_on`", but `is_ready` already requires every `depends_on` to
      be `done`, so two *ready* items can never depend on each other. That
      check is retained only as a safety net for force-advanced items —
      `touches:` is what actually does the work here.

### C2. Parallel implement, serial land
- [x] Orchestrator dispatches waves of up to 3 implementers; review, land,
      and QA stay strictly one at a time.
- [x] All `start` calls complete **before** any spawn — worktree isolation
      forks from committed state, so spawning between two `start`s shows an
      agent a half-updated board.
- [x] Orchestrator remains the sole writer of `tasks/`.
- [x] Merge-conflict path defined: re-spawn that item's implementer to
      rebase and push, land again, `blocked` on a second failure — the rest
      of the wave is unaffected. Repeated conflicts across a wave means
      dropping `--max` to 1 and saying so in the final report.

## Phase D — Design gate  ✅ DONE

### D1. Front-load structural questions
- [x] `gdo-design-reviewer` gains a required `## Unresolved design
      decisions` section — ranked, each with the choice, the options, and
      what each would change downstream.
- [x] It must end that section by stating plainly whether resolving all of
      them would leave nothing structural outstanding.
- [x] Round 1 is explicitly told to be exhaustive about decisions: the
      expensive failure mode is a *serialized* finding, not a wrong one.
- [x] `/gdo-gdd` presents those decisions to the user as one block rather
      than one at a time, via `AskUserQuestion` where the options are
      discrete.

### D2. Incremental review rounds
- [x] Rounds 2+ get the previous round's findings verbatim plus what
      changed, and are scoped to verifying those and catching what the
      edits introduced — not re-deriving a full critique of a document
      that keeps growing.
- [x] New `## Prior findings` output section, per-item resolved / NOT
      resolved.
- [x] `/gdo-gdd` notes that heading past round 3 is itself a signal that
      decisions are being surfaced one per round instead of together.

## Optional — GitHub Issues mirror (visibility, not speed)

Deliberately **not** load-bearing: `gdo_board.py` stays the source of truth.

- [ ] `gdo_board.py sync-issues` — push board state to GitHub Issues
      (create/update/close, status as labels), run **once per epic**, not
      per transition.
- [ ] PR bodies gain `Closes #N` so merges close the mirrored issue.

---

## Expected outcome

| | before | after A | after A+B | after A+B+C |
|---|---|---|---|---|
| orchestrator calls/ticket | ~20 | ~5 | ~5 | ~5 |
| sub-agent spawns/ticket | 3 | 3 | ~2.3 | ~2.3 |
| rediscovery calls/spawn | ~5 | ~0 | ~0 | ~0 |
| commits/push per QA'd batch of 3 | 3 + 3 | 3 + 3 | 1 + 1 | 1 + 1 |
| epic wall-clock | baseline | lower | lower | ~halved where tickets are independent |

Phase D is separate: it targets the design gate, where the first run spent
4 review rounds on what were 4 serialized design decisions. Expected 4 → 2.

**None of this is measured yet.** The numbers above are derived from call
counts in the rewritten skills, not from a second full run. The honest test
is running an epic end to end on a real project and comparing.
