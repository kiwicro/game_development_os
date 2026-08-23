---
name: gdo-board
description: Show current status of the design docs, epics, and tickets — what's ready to start, what's blocked and why, PR links. Use whenever the user asks for project status, what's ready, or what's blocked.
user-invocable: true
allowed-tools: Bash(python .claude/scripts/gdo_board.py:*)
---

# /gdo-board — Status View

Arguments passed: `$ARGUMENTS` — optionally an epic ID (e.g. `EPIC-002`) to
filter to just that epic.

Run:

```
python .claude/scripts/gdo_board.py board [--epic <ID>]
```

Show the output to the user essentially as-is — it's already organized to
be scanned, not read top-to-bottom: a `NEEDS ATTENTION` section up front
(anything `blocked`, plus anything at `attempts: 2` that's one rejection or
regression away from blocking) before the per-epic detail, so what actually
needs a human is visible without reading every ticket. Add narration only
where it's genuinely useful — e.g. if something is `ready-to-start` and
`/gdo-run` hasn't been used on that epic yet, mention it; if `NEEDS
ATTENTION` isn't empty, lead with that rather than burying it after the
full listing.

If `tasks/epics/` is empty, the script says so — point the user at
`/gdo-gdd` → `/gdo-mvp` → `/gdo-epic` as the path to get there.

Don't hand-parse `tasks/*.md` yourself for this — the script is the source
of truth for computed state (ready/blocked/cycles); reading the raw files
by eye risks disagreeing with it.
