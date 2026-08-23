---
id: ART-NNN
epic: EPIC-NNN
title: <short title>
status: backlog
depends_on: []
attempts: 0
pr_url: null
owner_agent: null
created: <YYYY-MM-DD>
---

## Spec

What's needed: asset type (sprite / texture / icon / UI element / audio /
model), target path in the project, dimensions or format, and any style
notes. Be concrete enough that "does this meet the spec" is checkable —
same bar as a code ticket's acceptance criteria.

## Acceptance criteria

- File exists at `<path>`, correct format and dimensions.
- If placeholder art (the default — see `CLAUDE.md`): filename or path
  clearly marks it as a placeholder (e.g. `*.placeholder.png`) so it's easy
  to find and swap later.
- Loads correctly in the engine, where that's checkable without engine
  tooling this framework doesn't have wired up.

## Notes

Real-art follow-up needed? A placeholder ticket should say so explicitly
here so it isn't mistaken for finished art.
