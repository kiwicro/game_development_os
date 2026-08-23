---
name: gdo-gdd
description: Interview the user to draft or revise the Game Design Document at docs/gdd.md, then gate it through the gdo-design-reviewer subagent before it can be approved. Use when the user wants to start, continue, or revise a game's design doc.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Agent, AskUserQuestion
---

# /gdo-gdd — Game Design Document

Arguments passed: `$ARGUMENTS` (usually empty; may contain a game concept
the user wants to start from).

Read `CLAUDE.md` in the repo root first if you haven't already this session
— it defines conventions this skill depends on.

## State check

Read `docs/gdd.md` if it exists (check the YAML frontmatter `status`).
Branch:

- **No file** → go to *Fresh interview*.
- **status: draft** → tell the user you're resuming a draft, briefly
  summarize what's there, and continue the interview/drafting from where it
  left off.
- **status: in-review** → a review cycle was interrupted. Show the last
  entry in the `## Review Log` section and ask the user how they want to
  proceed (revise further, or re-run the review as-is).
- **status: approved** → tell the user the GDD is already approved and ask
  if they want to open it for revision. If yes: this is a real edit, not a
  rubber stamp — set `status: draft` and continue as a resume. Make sure the
  user understands revising will require passing the design review again
  before `/gdo-mvp` will run.

## Fresh interview

This is a design conversation, not a form. Don't fire off ten questions in
one message — ask a few at a time (AskUserQuestion where the options are
genuinely discrete choices, plain conversation where they aren't), react to
what the user says, and push back gently on vagueness ("fun exploration
game" isn't a pillar — what does the player *do*?). Cover, in whatever order
makes sense given how the conversation goes:

- **Concept & hook** — what is this, in one or two sentences? What's the "X
  meets Y" comparison, if there is one, and does it actually hold up
  mechanically?
- **Pillars** — 3–5 things the game is always true to. These are the
  yardstick every later scope decision gets measured against.
- **Core loop** — what the player does second-to-second/minute-to-minute,
  and why it's fun on its own merits.
- **Systems** — the handful of systems that support the loop (combat,
  economy, progression, AI, whatever's relevant). Don't let this balloon
  into a full spec at this stage — one or two sentences per system is
  enough for a GDD; systems get their own detail at ticket time.
- **Audience & platform** — who this is for, and where it runs.
- **Scope & constraints** — team size, timeline, budget, engine, anything
  real that bounds what's achievable. If the user doesn't know yet, say so
  explicitly in the doc rather than omitting the section — an unstated
  constraint is invisible to the reviewer and to future-you.
- **Known risks** — ask directly: what about this worries you?

## Drafting docs/gdd.md

```yaml
---
status: draft
version: 1
last_reviewed: null
---
```

Body sections: `## Pitch`, `## Pillars`, `## Core Loop`, `## Systems`,
`## Audience & Platform`, `## Scope & Constraints`, `## Risks`,
`## Open Questions`, `## Review Log` (empty until a review runs).

Show the user the draft (or a summary of what changed, on revisions) and
iterate until they say it's ready for review. Bump `version` on each
substantive revision after the first review has run.

## Design review gate

When the user says the draft is ready:

1. Set `status: in-review`, save.
2. Spawn the `gdo-design-reviewer` subagent (fresh context — it should not
   see this drafting conversation) with a prompt pointing it at
   `docs/gdd.md` in this repo and asking it to apply its review lens and
   return its verdict.
3. Append a new entry to `## Review Log` in `docs/gdd.md`:
   ```
   ### Round N — <date> — <verdict>
   <findings, condensed>
   Resolution: pending
   ```
4. Present the reviewer's findings to the user in full (don't summarize
   away the concerns) and discuss them like a design partner would — you
   can share your own read, but the call is the user's.
5. Ask the user how to proceed:
   - **Revise** — go back to drafting with the reviewer's concerns as the
     agenda, then automatically re-run the review (repeat this gate) once
     they say it's ready again. Update the log entry's resolution to
     `revised → round N+1`.
   - **Approve as-is** — valid whether the verdict was `approved`,
     `approved-with-notes`, or (the user overriding) `needs-revision`. If
     overriding a `needs-revision` verdict, record the user's reasoning in
     the log entry's resolution (`approved — override: <reasoning>`) —
     don't silently approve over a blocking verdict without capturing why.
6. On approval: set `status: approved`, `last_reviewed: <date>`, save. Tell
   the user `/gdo-mvp` is now unblocked.

This revise → re-review cycle repeats automatically (you don't need the user
to re-invoke the skill each round) up to **5 rounds**. If round 5 still
hasn't reached an approval, stop looping automatically: tell the user
plainly that five rounds haven't converged and ask directly whether they
want to keep iterating, override and approve, or step back and reconsider
the concept — don't keep cycling without them explicitly saying to.

## Ground rules

- Never set `status: approved` without the user explicitly saying to. You
  drafting a clean doc and a good verdict from the reviewer is not the same
  as the user approving it.
- Never let the reviewer's verdict alone flip the status — it's an input to
  the user's decision, not the decision.
- If the user tries to skip straight to `/gdo-mvp` from an unapproved GDD,
  that skill will refuse on its own; you don't need to enforce it here, but
  do mention the gate if they ask to jump ahead.
