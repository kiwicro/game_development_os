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

## Phase A — Foundations (no behavior change, pure call reduction)

### A1. Collapse the git+status dances into `gdo_board.py` subcommands
- [ ] `start <ID>` — `backlog→ready→in-progress` (chained), then
      `git add tasks/ && git commit -m "<ID>: mark in-progress"`.
      Add `--no-commit` for callers that batch.
- [ ] `opened <ID> --pr-url URL` — `→in-review` + commit.
- [ ] `land <ID>` — the full merge dance, in the one correct order:
      1. **Guard:** `git diff --name-only origin/main...ticket/<ID>-<slug> -- tasks/`
         must be empty. If not, exit non-zero listing the offending files —
         this is the BUG-002 collision class, caught *before* the merge.
      2. `gh pr merge <pr_url> --squash --delete-branch`
      3. `git pull --rebase origin main`
      4. `set-status <ID> merged` + commit + push
- [ ] `finish <ID> [--bug <file>...]` — `merged→qa→done`, file any bug
      files, commit, push.
- [ ] Every subcommand fails loudly and leaves state unchanged on error —
      no half-applied transitions.

**Verify:** run each against a scratch repo; `gdo_board.py validate` clean
afterward. **Payoff:** ~20 bookkeeping calls/ticket → ~5, and the merge
ordering becomes impossible to get wrong.

### A2. `gdo_board.py doctor` — reconcile frontmatter against git/gh reality
- [ ] For every item not `done`/`blocked`: does `ticket/<ID>-*` exist on
      origin? Is there a PR? Does its state match the frontmatter?
- [ ] Report drift as a table.
- [ ] `--fix`: reset `in-progress`-with-no-branch-and-no-PR back to `ready`.
- [ ] Call it at the top of `/gdo-run` on resume.

**Replaces:** the manual `git branch` / `git log` audit after each of the
two session-limit deaths.

### A3. Split `.claude/conventions.md` out of `CLAUDE.md`
- [ ] Extract only what sub-agents need: IDs/filenames, ticket frontmatter
      schema, status machine, branch/PR conventions, ground rules (~60 lines).
- [ ] `CLAUDE.md` keeps everything and links to it — orchestrator still
      reads the full file.

### A4. Agents accept a brief instead of re-reading everything
- [ ] Define the `## Brief` block: ticket body verbatim, branch name, PR
      URL, conventions, `docs/engine.md` contents.
- [ ] In `gdo-implementer.md`, `gdo-artist.md`, `gdo-reviewer.md`,
      `gdo-qa.md`: change "read `CLAUDE.md` in full" to — *if your prompt
      has a `## Brief`, it already carries this; don't re-read. Otherwise
      read `.claude/conventions.md`.*
- [ ] Keep the fallback path working for manual/ad-hoc spawns.

**Payoff:** ~5 rediscovery calls × 3 spawns × N tickets.

### A5. Rewire callers
- [ ] `gdo-orchestrator.md` — use A1 subcommands, emit A4 briefs.
- [ ] `/gdo-implement`, `/gdo-review`, `/gdo-qa-run` — same, so the manual
      path and the autonomous path stay identical.
- [ ] Update each skill's `allowed-tools` for the new subcommands.

### A6. `/gdo-setup` preflight — catch the two hard blockers
- [ ] Repo has ≥1 commit (`git rev-parse HEAD`).
- [ ] Remote has at least one branch (`git ls-remote --heads origin`).
- [ ] Local HEAD is actually pushed (no unpushed ahead-count).
- [ ] Offer to fix each in place rather than just reporting.

---

## Phase B — Fewer spawns per ticket

### B1. Conditional QA
- [ ] After `land`, check whether anything else merged since the branch
      point. If not, the squashed tree matches the reviewed tree — skip
      acceptance-criteria re-verification, run only the exploratory pass.

### B2. Batched per-epic QA
- [ ] One QA spawn per epic (or per 3 merges) covering all merged tickets'
      criteria plus one broader exploratory sweep, instead of N spawns.
- [ ] Keep per-ticket QA when the merge was non-trivial (conflict resolved,
      or another ticket merged in between).
- [ ] Bug-filing path unchanged — batching finds new bugs just as well.

### B3. Model per agent (frontmatter `model:`)
- [ ] `gdo-artist` → haiku (it calls a script).
- [ ] Keep opus on `gdo-design-reviewer` and `gdo-implementer`.
- [ ] Measure before fixing the rest.

### B4. Housekeeping
- [ ] One `gh pr view <n> --json state,mergeable,comments,url` instead of
      three separate calls.
- [ ] Reusable review worktree instead of a fresh one per ticket.
- [ ] `git worktree prune` in the orchestrator's *Finishing up* — the
      leftover undeletable `.claude/worktrees/agent-*` dirs.

---

## Phase C — Parallelism (biggest wall-clock lever, needs A first)

### C1. Independence check
- [ ] Given N `ready` tickets, determine which are safe to run concurrently:
      no shared `depends_on`, disjoint expected file footprints.
- [ ] Conservative default — when in doubt, serialize.

### C2. Parallel implement, serial land
- [ ] Replace the blanket "sequential, not parallel" rule in
      `gdo-orchestrator.md` with: fan out 2–3 implementers on independent
      ready tickets (art tickets parallelize freely with code tickets),
      then review + merge **one at a time** as reports arrive.
- [ ] Orchestrator remains the sole writer of `tasks/` — all status commits
      serialized between dispatch waves.
- [ ] The merge queue stays strictly serial.

---

## Phase D — Design gate (independent of A–C, can land anytime)

### D1. Front-load structural questions
- [ ] Add a required `## Unresolved design decisions` section to
      `gdo-design-reviewer.md` — exhaustive and ranked: *answer these and I
      have nothing structural left.*
- [ ] Round 1 surfaces all of them at once rather than one per round.

### D2. Incremental review rounds
- [ ] `/gdo-gdd` scopes rounds 2+ to "verify these were resolved + only
      what the edits newly broke" instead of a fresh full critique.

**Target:** 4 rounds → 2, and stops the per-round time climb (53s → 100s as
the doc grew).

---

## Optional — GitHub Issues mirror (visibility, not speed)

Deliberately **not** load-bearing: `gdo_board.py` stays the source of truth.

- [ ] `gdo_board.py sync-issues` — push board state to GitHub Issues
      (create/update/close, status as labels), run **once per epic**, not
      per transition.
- [ ] PR bodies gain `Closes #N` so merges close the mirrored issue.

---

## Expected outcome

| | now | after A | after A+B | after A+B+C |
|---|---|---|---|---|
| orchestrator calls/ticket | ~20 | ~5 | ~5 | ~5 |
| sub-agent spawns/ticket | 3 | 3 | ~2 | ~2 |
| rediscovery calls/spawn | ~5 | ~0 | ~0 | ~0 |
| epic wall-clock | baseline | lower | lower | ~halved on independent tickets |
