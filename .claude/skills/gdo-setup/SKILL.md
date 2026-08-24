---
name: gdo-setup
description: Install this framework into a game project, or finish configuring it once installed there - git/GitHub check, engine detection, optional engine-MCP guidance. Use when the user wants to connect Game Development OS to a game project, or start using GDO on a new project.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Bash, AskUserQuestion
---

# /gdo-setup — Connect GDO to a Game Project

Arguments passed: `$ARGUMENTS` — a target directory path, or empty.

This skill has two distinct modes, and which one runs depends on whether
you were given a path:

- **`$ARGUMENTS` is a path → Install mode.** You're running from inside
  *this* GDO repo, and copying the framework into a separate target project
  that doesn't have it yet.
- **`$ARGUMENTS` is empty → Configure mode.** You're already running inside
  a project that has the framework installed (this skill file had to be
  loaded from somewhere) — finish connecting it: git/GitHub, engine
  detection, MCP guidance.

A brand-new project usually needs Install once, then Configure (in a fresh
session opened in the target directory, since a session's skills load at
startup — see `CLAUDE.md`'s notes on this if you want the mechanical
reason). Re-running Configure later is safe and idempotent.

---

## Install mode

1. Confirm the target directory exists (`mkdir -p` it if the user wants a
   brand-new empty project). If it already has `.claude/skills/gdo-gdd/`,
   tell the user GDO looks already installed there and ask whether they
   want to overwrite (re-install) or stop.

2. Copy these paths from this repo into the target, preserving structure:

   ```
   .claude/skills/gdo-gdd/
   .claude/skills/gdo-mvp/
   .claude/skills/gdo-epic/
   .claude/skills/gdo-board/
   .claude/skills/gdo-implement/
   .claude/skills/gdo-review/
   .claude/skills/gdo-qa-run/
   .claude/skills/gdo-run/
   .claude/skills/gdo-setup/
   .claude/agents/gdo-design-reviewer.md
   .claude/agents/gdo-implementer.md
   .claude/agents/gdo-reviewer.md
   .claude/agents/gdo-qa.md
   .claude/agents/gdo-orchestrator.md
   .claude/agents/gdo-artist.md
   .claude/scripts/gdo_board.py
   .claude/scripts/gdo_placeholder_art.py
   tasks/_templates/epic.md
   tasks/_templates/ticket.md
   tasks/_templates/bug.md
   tasks/_templates/art.md
   ```

   Then create empty `tasks/epics/`, `tasks/tickets/`, `tasks/bugs/`,
   `tasks/art/` in the target (with a `.gitkeep` each, same as this repo)
   and a `docs/` directory — **don't** copy this repo's own
   `tasks/epics/EPIC-001-*`, `tasks/tickets/*`, `tasks/bugs/*`,
   `docs/gdd.md`, or `docs/mvp.md` — those are this framework's own
   dogfood/smoke-test data, not template content, and would confuse a
   fresh project.

3. `CLAUDE.md` — don't blindly overwrite. If the target has no `CLAUDE.md`,
   copy this repo's one as-is. If it already has one (real, pre-existing
   project conventions), read both and merge by hand: append this repo's
   content as a clearly delimited section (e.g. under a `## Game
   Development OS` heading) rather than replacing what's there — the
   target project's existing conventions matter and shouldn't get clobbered
   by a copy operation.

4. Confirm the copy with `Glob` (`tasks/_templates/*.md` and
   `.claude/skills/gdo-*` in the target should list everything from step 2).

5. Tell the user plainly: open a new Claude Code session **in the target
   directory** and run `/gdo-setup` there with no arguments to finish
   connecting it (git/GitHub, engine detection). This session, still
   running from the GDO repo, can't do that part — it isn't *in* the
   target project.

---

## Configure mode

Assumes you're running inside a project that already has the framework's
files (this skill itself loaded from `.claude/skills/gdo-setup/`).

### 1. Git and GitHub

Check `git status` in the current directory. If it's not a repo yet, ask
the user whether to `git init` it (mirroring how this framework's own repo
was set up — see `CLAUDE.md`'s git history if you want a concrete
reference). This is a **hard requirement**, not optional: every stage past
`/gdo-implement` depends on real `gh pr create`/`gh pr merge` calls against
a GitHub remote — there's no non-GitHub path built. If the user doesn't
want GitHub involved, say plainly that the autonomous execution half of
this framework (`/gdo-implement` onward) won't work without it; the design
half (`/gdo-gdd`, `/gdo-mvp`, `/gdo-epic`) still will.

Check for a remote (`git remote -v`) and that `gh auth status` succeeds. If
either is missing, offer to help set it up the same way: `gh repo create`
for a new GitHub repo, or `git remote add origin <url>` if the user already
has one. Confirm `gh` is authenticated before calling this step done.

**Then check the three things that actually block a run.** A repo can pass
every check above and still stop `/gdo-run` dead on its first ticket — this
happened on the first real project. "A remote is configured" is not the
same as "there is anything on it." All three are one command each, and all
three are fixable in place:

| Check | Command | Why it blocks |
|---|---|---|
| Repo has ≥1 commit | `git rev-parse HEAD` | `Agent` calls with `isolation: "worktree"` fork from **committed** git state. With zero commits, every implementer you spawn gets an empty worktree — no GDD, no tickets, no project files. |
| Remote has ≥1 branch | `git ls-remote --heads origin` | `gh pr create` needs a base branch that exists on the remote. An empty repo on GitHub has none, so the first PR can't be opened at all. |
| HEAD is pushed | `git status -sb` (look for `ahead`) | Local commits the remote hasn't seen aren't in the PR base. Reviewers and QA then test against a tree that's missing work you think landed. |

Offer to fix each in place rather than just reporting it: `git add -A && git
commit` for the first, `git push -u origin <branch>` for the other two.
Don't call this step done with any of the three unresolved — say plainly
that `/gdo-run` will fail on its first ticket otherwise.

### 2. Engine detection

`Glob` for markers, in this order (first match wins — a project could
technically have stray files from more than one):

| Marker | Engine |
|---|---|
| `project.godot` | Godot |
| `*.uproject` | Unreal |
| `Assets/` **and** `ProjectSettings/` both present | Unity |
| none of the above | ask the user, or record "unspecified" if they don't know yet |

Write (or update) `docs/engine.md`:

```markdown
# Engine

Detected: <Godot | Unreal | Unity | unspecified>
MCP: <not connected | connected — see notes below>
```

### 3. Engine MCP — guidance only, always skippable

This framework does **not** hard-wire any engine-specific tool calls into
`gdo-implementer`/`gdo-reviewer`/`gdo-qa`/`gdo-artist` — they use whatever
tools are actually available in their session, generically. This step is
purely informational; tell the user they can skip it entirely and nothing
downstream breaks.

- **Godot**: mention that Godot has a known MCP integration (scene/node
  creation, running/debugging projects, sprite loading) some environments
  already have connected — check `claude mcp list` or the project's
  `.mcp.json`. If one's connected, note it in `docs/engine.md`'s `MCP:`
  line; GDO's agents will notice and use it naturally where it's the
  obvious tool for the job (e.g. running the project to verify a change)
  since they aren't restricted from it.
- **Unity / Unreal**: no MCP integration verified from here — don't
  fabricate specific tool or package names. If the user's team already uses
  one, point them at configuring it the standard way (`.mcp.json` in the
  project, or `claude mcp add`) and note it in `docs/engine.md`. Otherwise,
  say this is worth revisiting later and move on — it's not a blocker for
  anything.
- **Unspecified**: skip this step entirely.

### 4. Verify

Run `python .claude/scripts/gdo_board.py validate` — should report a clean,
empty tree (`OK`, no epics yet). If it errors, something copied wrong;
diagnose before telling the user setup succeeded.

Then run `python .claude/scripts/gdo_board.py doctor`. On a fresh setup it
should report `OK` with nothing to reconcile; it's worth running once here
so the command is known-working before a real run depends on it (it needs
`gh` authenticated, which is exactly what step 1 just established).

### 5. Hand off

Tell the user plainly: setup's done, `/gdo-gdd` is the next step whenever
they're ready to start designing.

## Ground rules

- Never invent MCP tool/package names you haven't actually verified exist
  in the current environment — say "check X" rather than naming a specific
  integration you're not sure is real.
- Never silently overwrite an existing `CLAUDE.md`, `docs/gdd.md`, or
  `docs/mvp.md` in a target project — always read first, merge or ask.
- GitHub is a hard requirement for execution, not a soft recommendation —
  don't imply the framework works without it past the design stage.
- "Configured" is not "working": a remote that exists but is empty, or a
  repo with no commits, passes a naive check and still breaks the first
  ticket. Verify the three blockers in step 1 by running them, not by
  assuming.
