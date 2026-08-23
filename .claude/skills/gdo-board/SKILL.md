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

Show the output to the user essentially as-is — it's already organized
(design doc status, per-epic ticket counts, then each epic's tickets with
`ready-to-start` or a blocked reason). Add narration only where it's
genuinely useful: e.g. if something is ready to start and autonomous
execution exists yet, mention it; if a ticket has been sitting `blocked`
because of exhausted attempts, flag that clearly since it means a human
decision is needed.

If `tasks/epics/` is empty, the script says so — point the user at
`/gdo-gdd` → `/gdo-mvp` → `/gdo-epic` as the path to get there.

Don't hand-parse `tasks/*.md` yourself for this — the script is the source
of truth for computed state (ready/blocked/cycles); reading the raw files
by eye risks disagreeing with it.
