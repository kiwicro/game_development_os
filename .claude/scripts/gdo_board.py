#!/usr/bin/env python3
"""
Game Development OS — task board helper.

Deterministic reader/writer for the frontmatter in tasks/epics/*.md,
tasks/tickets/*.md, tasks/bugs/*.md, tasks/art/*.md. Skills and agents
should shell out to this instead of hand-parsing YAML — it's the single
place that knows the schema and the status machine defined in CLAUDE.md.

No third-party dependencies (stdlib only), so it runs anywhere Python 3.8+
is available, independent of whatever engine/language the game itself uses.

Commands:
  board [--epic EPIC-ID] [--json]     Render current status.
  ready --epic EPIC-ID [--json]       List ticket/bug/art IDs eligible to start now.
  next-id <EPIC|TICKET|BUG|ART>       Print the next free ID for that prefix.
  set-status <ID> <new-status>        Update a ticket/bug/art/epic's status, validating
                                       the transition against the state machine.
                                       [--pr-url URL] [--attempts N] [--owner NAME]
                                       [--force]  (bypass transition validation)
  cycles                              Report dependency cycles among tickets/bugs/art.
  validate                            Sanity-check the whole tasks/ tree.

Workflow commands - each wraps a multi-step git+status sequence that used to be
spelled out call-by-call in the skills, so the ordering can't be gotten wrong:
  start <ID>                          backlog/ready -> in-progress, committed.
  opened <ID> --pr-url URL            -> in-review, PR recorded, committed.
  land <ID>                           Guard branch against tasks/ edits, squash-merge,
                                       rebase-pull, -> merged, commit, push.
  finish <ID> [--bug PATH ...]        -> qa -> done (+ file QA's bugs), commit, push.
  doctor [--epic E] [--fix]           Reconcile frontmatter against real git/gh state.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Windows consoles default to a legacy codepage that mangles em-dashes etc.
# Force UTF-8 stdout/stderr so output is consistent across platforms.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS = REPO_ROOT / "tasks"
EPICS_DIR = TASKS / "epics"
TICKETS_DIR = TASKS / "tickets"
BUGS_DIR = TASKS / "bugs"
ART_DIR = TASKS / "art"

# Item directories, keyed by ID prefix. TICKET, BUG, and ART all share the
# same status machine and frontmatter shape (ART is functionally "a ticket
# whose implement stage is art sourcing, not code" — see CLAUDE.md) — kept
# as separate directories/prefixes purely so a human scanning tasks/ sees
# code work, bugs, and art work as distinct piles.
ITEM_DIRS = {"TICKET": TICKETS_DIR, "BUG": BUGS_DIR, "ART": ART_DIR}

ID_RE = re.compile(r"^(EPIC|TICKET|BUG|ART)-(\d+)-")

# Ticket/bug status machine. Every status may also move to "blocked"
# (side-state, entered from anywhere) — that's handled separately, not
# listed per-row below.
TICKET_TRANSITIONS = {
    "backlog": {"ready"},
    "ready": {"in-progress"},
    "in-progress": {"in-review"},
    "in-review": {"merged", "changes-requested"},
    "changes-requested": {"in-progress"},
    "merged": {"qa"},
    "qa": {"done", "in-progress"},  # in-progress: QA found the merged change itself doesn't meet acceptance criteria
    "done": set(),
    "blocked": {"backlog", "in-progress"},
}
TICKET_STATUSES = set(TICKET_TRANSITIONS) | {"blocked"}

EPIC_TRANSITIONS = {
    "draft": {"ready"},
    "ready": {"in-progress", "draft"},
    "in-progress": {"done", "ready"},
    "done": set(),
}
EPIC_STATUSES = set(EPIC_TRANSITIONS)


# ---------------------------------------------------------------------------
# Minimal frontmatter parsing (hand-rolled: our schema is flat scalars plus
# one list field, so a full YAML library is unneeded weight).
# ---------------------------------------------------------------------------

def split_frontmatter(text):
    """Return (frontmatter_lines, body_text, fm_start_idx, fm_end_idx) or
    None if the file has no --- delimited frontmatter."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "".join(lines[i + 1:]), 0, i
    return None


def parse_scalar(raw):
    raw = raw.strip()
    if raw == "" or raw == "null" or raw == "~":
        return None
    if raw == "[]":
        return []
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [v.strip().strip("'\"") for v in inner.split(",")]
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    return raw


def parse_frontmatter(fm_lines):
    """Parse frontmatter lines into an ordered dict of key -> value,
    supporting inline scalars/lists and block-style `key:\n  - item` lists."""
    data = {}
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line.rstrip("\n"))
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2)
        if rest == "":
            # possible block list on following indented lines
            items = []
            j = i + 1
            while j < len(fm_lines) and re.match(r"^\s+-\s+", fm_lines[j]):
                items.append(fm_lines[j].strip()[2:].strip().strip("'\""))
                j += 1
            if items:
                data[key] = items
                i = j
                continue
            data[key] = None
            i += 1
            continue
        data[key] = parse_scalar(rest)
        i += 1
    return data


def load_task_file(path):
    text = path.read_text(encoding="utf-8")
    split = split_frontmatter(text)
    if split is None:
        return None
    fm_lines, body, _, _ = split
    fm = parse_frontmatter(fm_lines)
    fm["_path"] = path
    fm["_body"] = body
    return fm


def set_frontmatter_field(path, key, value):
    """Rewrite a single scalar frontmatter field in place, byte-identical
    elsewhere. Only safe for scalar fields (status, pr_url, attempts,
    owner_agent) — not list fields."""
    text = path.read_text(encoding="utf-8")
    split = split_frontmatter(text)
    if split is None:
        raise ValueError(f"{path}: no frontmatter block found")
    fm_lines, body, _, _ = split

    formatted = "null" if value is None else str(value)
    pattern = re.compile(rf"^{re.escape(key)}:\s*.*$")
    found = False
    new_lines = []
    for line in fm_lines:
        if pattern.match(line.rstrip("\n")):
            new_lines.append(f"{key}: {formatted}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}: {formatted}\n")

    new_text = "---\n" + "".join(new_lines) + "---\n" + body
    path.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Loading the whole tree
# ---------------------------------------------------------------------------

def load_all():
    epics = {}
    for p in sorted(EPICS_DIR.glob("EPIC-*.md")):
        fm = load_task_file(p)
        if fm and fm.get("id"):
            epics[fm["id"]] = fm

    items = {}  # tickets + bugs + art, keyed by id
    for directory in ITEM_DIRS.values():
        for p in sorted(directory.glob("*.md")):
            if p.name.startswith("_"):
                continue
            fm = load_task_file(p)
            if fm and fm.get("id"):
                items[fm["id"]] = fm
    return epics, items


def is_ready(item, epics, items):
    if item.get("status") not in ("backlog", "ready"):
        return False
    epic = epics.get(item.get("epic"))
    if not epic or epic.get("status") not in ("ready", "in-progress"):
        return False
    for dep in item.get("depends_on") or []:
        dep_item = items.get(dep)
        if not dep_item or dep_item.get("status") != "done":
            return False
    return True


def blocked_reason(item, epics, items):
    if item.get("status") == "blocked":
        return "marked blocked"
    epic = epics.get(item.get("epic"))
    if not epic:
        return f"unknown epic {item.get('epic')}"
    if epic.get("status") not in ("ready", "in-progress"):
        return f"epic {epic.get('id')} is {epic.get('status')}"
    unmet = [
        dep for dep in (item.get("depends_on") or [])
        if not items.get(dep) or items[dep].get("status") != "done"
    ]
    if unmet:
        return f"waiting on {', '.join(unmet)}"
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_next_id(args):
    prefix = args.prefix.upper()
    directory = {"EPIC": EPICS_DIR, **ITEM_DIRS}.get(prefix)
    if directory is None:
        print(f"error: prefix must be EPIC, TICKET, BUG, or ART (got {args.prefix})", file=sys.stderr)
        return 1
    max_n = 0
    for p in directory.glob(f"{prefix}-*.md"):
        m = ID_RE.match(p.name)
        if m:
            max_n = max(max_n, int(m.group(2)))
    print(f"{prefix}-{max_n + 1:03d}")
    return 0


def cmd_ready(args):
    epics, items = load_all()
    epic_id = args.epic
    if epic_id and epic_id not in epics:
        print(f"error: unknown epic {epic_id}", file=sys.stderr)
        return 1
    result = [
        iid for iid, item in items.items()
        if (not epic_id or item.get("epic") == epic_id) and is_ready(item, epics, items)
    ]
    if args.json:
        print(json.dumps(result))
    else:
        for r in result:
            print(r)
    return 0


def cmd_set_status(args):
    """Thin CLI wrapper over apply_transition - kept for single, explicit
    transitions and for anything the workflow commands below don't cover."""
    try:
        apply_transition(
            args.id, args.status, force=args.force,
            pr_url=args.pr_url, attempts=args.attempts, owner_agent=args.owner,
        )
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_cycles(args):
    _, items = load_all()
    visited, stack = set(), []
    found = []

    def dfs(node_id, path):
        if node_id in path:
            cyc = path[path.index(node_id):] + [node_id]
            found.append(cyc)
            return
        if node_id in visited:
            return
        visited.add(node_id)
        item = items.get(node_id)
        if not item:
            return
        for dep in item.get("depends_on") or []:
            dfs(dep, path + [node_id])

    for iid in items:
        dfs(iid, [])

    if found:
        for cyc in found:
            print(" -> ".join(cyc))
        return 1
    print("no cycles detected")
    return 0


def cmd_validate(args):
    epics, items = load_all()
    errors = []

    dir_to_prefix = {d: p for p, d in ITEM_DIRS.items()}
    for iid, item in items.items():
        expected_prefix = dir_to_prefix.get(item["_path"].parent, "TICKET")
        if not iid.startswith(expected_prefix + "-"):
            errors.append(f"{item['_path'].name}: id {iid} doesn't match its directory ({expected_prefix})")
        stem_id = item["_path"].name.split("-", 2)
        if len(stem_id) >= 2:
            filename_id = f"{stem_id[0]}-{stem_id[1]}"
            if filename_id != iid:
                errors.append(f"{item['_path'].name}: filename id {filename_id} != frontmatter id {iid}")
        epic_ref = item.get("epic")
        if epic_ref not in epics:
            errors.append(f"{iid}: references unknown epic {epic_ref}")
        for dep in item.get("depends_on") or []:
            if dep not in items:
                errors.append(f"{iid}: depends_on unknown id {dep}")
        if item.get("status") not in TICKET_STATUSES:
            errors.append(f"{iid}: invalid status {item.get('status')!r}")

    for eid, epic in epics.items():
        if epic.get("status") not in EPIC_STATUSES:
            errors.append(f"{eid}: invalid status {epic.get('status')!r}")

    cyc_rc = cmd_cycles(argparse.Namespace())
    if cyc_rc != 0:
        errors.append("dependency cycle(s) detected (see above)")

    if errors:
        print(f"\n{len(errors)} problem(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("OK — tasks/ tree is internally consistent")
    return 0


def cmd_board(args):
    epics, items = load_all()
    epic_filter = args.epic

    def status_summary(status_bucket):
        counts = {}
        for it in status_bucket:
            counts[it["status"]] = counts.get(it["status"], 0) + 1
        return counts

    def needs_attention(i):
        if i.get("status") == "blocked":
            return "blocked"
        attempts = i.get("attempts") or 0
        if isinstance(attempts, int) and attempts >= 2 and i.get("status") != "done":
            return f"attempt {attempts}/3 — one more rejection/regression blocks this"
        return None

    if args.json:
        out = {"epics": {}, "design_docs": {}, "needs_attention": {}}
        for eid, epic in epics.items():
            if epic_filter and eid != epic_filter:
                continue
            eitems = [i for i in items.values() if i.get("epic") == eid]
            out["epics"][eid] = {
                "title": epic.get("title"),
                "status": epic.get("status"),
                "tickets": {
                    iid: {
                        "title": i.get("title"),
                        "status": i.get("status"),
                        "attempts": i.get("attempts") or 0,
                        "ready": is_ready(i, epics, items),
                        "blocked_reason": blocked_reason(i, epics, items) if not is_ready(i, epics, items) else None,
                        "pr_url": i.get("pr_url"),
                    }
                    for iid, i in items.items() if i.get("epic") == eid
                },
            }
            for iid, i in items.items():
                if i.get("epic") != eid:
                    continue
                attn = needs_attention(i)
                if attn:
                    out["needs_attention"][iid] = attn
        print(json.dumps(out, indent=2))
        return 0

    print("=== Game Development OS — Board ===\n")

    attention_items = [
        (iid, i) for iid, i in sorted(items.items())
        if (not epic_filter or i.get("epic") == epic_filter) and needs_attention(i)
    ]
    if attention_items:
        print("NEEDS ATTENTION:")
        for iid, i in attention_items:
            why = needs_attention(i)
            pr = f" — {i['pr_url']}" if i.get("pr_url") else ""
            print(f"  {iid:<10} [{i.get('status'):<18}] {why}{pr}")
        print()

    gdd_path = REPO_ROOT / "docs" / "gdd.md"
    mvp_path = REPO_ROOT / "docs" / "mvp.md"
    gdd = load_task_file(gdd_path) if gdd_path.exists() else None
    mvp = load_task_file(mvp_path) if mvp_path.exists() else None
    print("Design docs:")
    print(f"  GDD  : {gdd.get('status') if gdd else 'not started'}"
          + (f" (v{gdd.get('version')})" if gdd and gdd.get("version") else ""))
    print(f"  MVP  : {mvp.get('status') if mvp else 'not started'}")
    print()

    if not epics:
        print("No epics yet. Run /gdo-epic once the MVP is approved.")
        return 0

    print("Epics:")
    for eid, epic in sorted(epics.items()):
        if epic_filter and eid != epic_filter:
            continue
        eitems = [i for i in items.values() if i.get("epic") == eid]
        counts = status_summary(eitems)
        breakdown = ", ".join(f"{n} {s}" for s, n in sorted(counts.items(), key=lambda kv: -kv[1])) or "no tickets"
        print(f"  {eid:<10} {epic.get('title', ''):<28} [{epic.get('status'):<11}] {breakdown}")
    print()

    for eid, epic in sorted(epics.items()):
        if epic_filter and eid != epic_filter:
            continue
        eitems = sorted((i for i in items.values() if i.get("epic") == eid), key=lambda i: i["id"])
        print(f"{eid} — {epic.get('title', '')} [{epic.get('status')}]")
        if not eitems:
            print("  (no tickets yet)")
        for i in eitems:
            if i.get("status") == "done":
                marker = ""
            else:
                ready = is_ready(i, epics, items)
                tag = "ready-to-start" if ready else (blocked_reason(i, epics, items) or "")
                marker = f"  <- {tag}" if ready else (f"  ({tag})" if tag else "")
            attempts = i.get("attempts") or 0
            attempt_tag = f" [attempt {attempts}/3]" if attempts else ""
            pr_tag = f"  {i['pr_url']}" if i.get("pr_url") else ""
            print(f"  {i['id']:<10} [{i.get('status'):<18}] {i.get('title', ''):<32}{attempt_tag}{marker}{pr_tag}")
        print()

    return 0


# ---------------------------------------------------------------------------
# Workflow commands (start / opened / land / finish / doctor)
#
# These wrap the multi-step git+status sequences the skills used to spell out
# call-by-call. Two reasons they live here rather than in prose:
#   1. Call count - a ticket's bookkeeping drops from ~20 tool calls to ~5.
#   2. Ordering - `land` in particular has a sequence (guard, merge, rebase,
#      commit, push) that is easy to get wrong by hand and was gotten wrong in
#      practice. Encoding it once makes it unskippable.
# Every one of them validates and fails loudly *before* mutating anything, so a
# failed run leaves the tree exactly as it found it.
# ---------------------------------------------------------------------------

class WorkflowError(Exception):
    """A precondition failed. Raised before any mutation has happened."""


def run(cmd, check=True):
    proc = subprocess.run(
        cmd, cwd=str(REPO_ROOT), text=True, capture_output=True,
        encoding="utf-8", errors="replace",
    )
    if check and proc.returncode != 0:
        detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
        raise WorkflowError(f"command failed: {' '.join(cmd)}\n{detail}")
    return proc


def default_branch():
    """origin's default branch - main, master, or whatever this repo uses."""
    p = run(["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], check=False)
    if p.returncode == 0 and p.stdout.strip():
        return p.stdout.strip().rsplit("/", 1)[-1]
    for cand in ("main", "master"):
        if run(["git", "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{cand}"], check=False).returncode == 0:
            return cand
    return run(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=False).stdout.strip() or "main"


def branch_for(item):
    """Branch name per CLAUDE.md: ticket/<ID>-<slug>, matching the filename."""
    return "ticket/" + item["_path"].stem


def resolve_ref(branch):
    for ref in (f"origin/{branch}", branch):
        if run(["git", "rev-parse", "--verify", "--quiet", ref + "^{commit}"], check=False).returncode == 0:
            return ref
    return None


def rel(path):
    return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")


def git_commit(paths, message):
    """Stage exactly `paths` and commit. No-op (reported) if nothing changed."""
    paths = list(paths)
    run(["git", "add", "--"] + paths)
    if run(["git", "diff", "--cached", "--quiet", "--"] + paths, check=False).returncode == 0:
        print(f"  nothing to commit for: {message}")
        return False
    run(["git", "commit", "-m", message])
    print(f"  committed: {message}")
    return True


def require_item(items, target_id):
    if target_id not in items:
        raise WorkflowError(f"unknown id {target_id}")
    return items[target_id]


def apply_transition(target_id, new_status, force=False, **fields):
    """Validate one transition against the state machine, then write it.

    Shared by `set-status` and every workflow command below, so there is
    exactly one implementation of "is this legal"."""
    epics, items = load_all()
    is_epic = target_id.startswith("EPIC-")
    store = epics if is_epic else items
    if target_id not in store:
        raise WorkflowError(f"unknown id {target_id}")
    item = store[target_id]
    current = item.get("status")

    valid = EPIC_STATUSES if is_epic else TICKET_STATUSES
    if new_status not in valid:
        raise WorkflowError(
            f"'{new_status}' is not a valid status for {'an epic' if is_epic else 'a ticket/bug'}"
        )
    if not force and new_status != current:
        if is_epic:
            allowed = EPIC_TRANSITIONS.get(current, set())
        else:
            allowed = TICKET_TRANSITIONS.get(current, set()) | ({"blocked"} if new_status == "blocked" else set())
        if new_status not in allowed:
            raise WorkflowError(
                f"{target_id} cannot move {current} -> {new_status} "
                f"(allowed: {sorted(allowed) or '(none)'}). Use --force to override."
            )

    set_frontmatter_field(item["_path"], "status", new_status)
    for key, value in fields.items():
        if value is not None:
            set_frontmatter_field(item["_path"], key, value)
    print(f"{target_id}: {current} -> {new_status}")
    return item, current


def cmd_start(args):
    """backlog/ready -> in-progress, committed.

    Replaces the two set-status calls plus git add/commit that every dispatch
    used to spell out, and guarantees the commit actually happens - worktree
    agents fork from committed state, so a skipped commit hands the agent a
    stale ticket."""
    _, items = load_all()
    item = require_item(items, args.id)
    current = item.get("status")
    path = rel(item["_path"])

    if current == "in-progress":
        print(f"{args.id}: already in-progress")
    elif current == "backlog":
        apply_transition(args.id, "ready", force=args.force)
        apply_transition(args.id, "in-progress", force=args.force, owner_agent=args.owner)
    elif current in ("ready", "changes-requested", "blocked") or args.force:
        apply_transition(args.id, "in-progress", force=args.force, owner_agent=args.owner)
    else:
        raise WorkflowError(
            f"{args.id} is {current} - `start` expects backlog/ready/changes-requested/blocked. "
            f"Use --force if this is deliberate rework."
        )

    if not args.no_commit:
        git_commit([path], f"{args.id}: mark in-progress")
    return 0


def cmd_opened(args):
    """in-progress -> in-review, recording the PR URL, committed."""
    _, items = load_all()
    item = require_item(items, args.id)
    if not args.pr_url:
        raise WorkflowError("--pr-url is required")
    path = rel(item["_path"])
    apply_transition(args.id, "in-review", force=args.force, pr_url=args.pr_url)
    if not args.no_commit:
        git_commit([path], f"{args.id}: PR opened")
    return 0


def cmd_land(args):
    """The full merge sequence, in the one order that works.

    The guard runs first, and on failure nothing is merged or written: a branch
    carrying tasks/** changes is a process violation (only this script moves
    board state) and merging it collides with the orchestrator's own status
    commit on the default branch."""
    _, items = load_all()
    item = require_item(items, args.id)
    current = item.get("status")
    if current != "in-review" and not args.force:
        raise WorkflowError(f"{args.id} is {current} - `land` expects in-review. Use --force to override.")

    pr = args.pr_url or item.get("pr_url")
    if not pr:
        raise WorkflowError(f"{args.id} has no pr_url recorded - pass --pr-url explicitly")

    base = default_branch()
    branch = branch_for(item)
    path = rel(item["_path"])

    run(["git", "fetch", "origin", "--prune"], check=False)

    # --- Guard, before anything is merged ---------------------------------
    # Both refs must actually resolve. A guard that quietly skips itself when
    # it can't find a ref is worse than no guard - it reports success while
    # checking nothing - so an unresolvable ref is a hard error unless the
    # caller explicitly passed --force.
    base_ref = resolve_ref(base)
    ref = resolve_ref(branch)
    if base_ref is None or ref is None:
        missing = base if base_ref is None else branch
        if not args.force:
            raise WorkflowError(
                f"{args.id}: cannot resolve {missing} locally or on origin, so the tasks/ "
                f"guard cannot run. Fetch the branch first, or pass --force to merge anyway."
            )
        print(f"  warning: --force with {missing} unresolvable - tasks/ guard SKIPPED")
    else:
        diff = run(["git", "diff", "--name-only", f"{base_ref}...{ref}", "--", "tasks/"])
        offenders = [ln for ln in diff.stdout.splitlines() if ln.strip()]
        if offenders:
            raise WorkflowError(
                f"{args.id}: branch {branch} modifies tasks/ - only gdo_board.py may change board state.\n"
                + "\n".join(f"  {f}" for f in offenders)
                + "\nRevert those files on the branch (or drop the commit) and re-run `land`."
            )

    # --- Merge, resync, record --------------------------------------------
    run(["gh", "pr", "merge", pr, "--squash", "--delete-branch"])
    print(f"  merged {pr}")
    run(["git", "pull", "--rebase", "origin", base])
    apply_transition(args.id, "merged", force=args.force)
    git_commit([path], f"{args.id}: merged")
    if not args.no_push:
        run(["git", "push"])
        print("  pushed")
    return 0


def cmd_finish(args):
    """merged -> qa -> done, plus any bug files QA filed, committed and pushed.

    Clean-QA path only. A regression reopens the ticket instead, which the
    caller does with set-status plus an edit to the ticket body."""
    _, items = load_all()
    item = require_item(items, args.id)
    current = item.get("status")
    paths = [rel(item["_path"])]
    for bug_path in args.bug or []:
        candidate = REPO_ROOT / bug_path
        if not candidate.exists():
            raise WorkflowError(f"bug file not found: {bug_path}")
        paths.append(rel(candidate))

    if current == "merged":
        apply_transition(args.id, "qa", force=args.force)
    elif current != "qa":
        raise WorkflowError(f"{args.id} is {current} - `finish` expects merged or qa")
    apply_transition(args.id, "done", force=args.force)

    msg = f"{args.id}: QA passed, done"
    if args.bug:
        msg += f" (+{len(args.bug)} bug{'s' if len(args.bug) > 1 else ''} filed)"
    git_commit(paths, msg)
    if not args.no_push:
        run(["git", "push"])
        print("  pushed")
    return 0


def cmd_doctor(args):
    """Reconcile frontmatter against actual git/gh reality.

    Answers the question every resumed run has: is this ticket's status telling
    the truth? A session that dies between `start` and dispatch leaves
    `in-progress` with no branch and no PR - nothing was lost, but the status
    lies. Two network calls total, regardless of ticket count."""
    _, items = load_all()

    run(["git", "fetch", "origin", "--prune"], check=False)
    remote_branches = set()
    ls = run(["git", "ls-remote", "--heads", "origin"], check=False)
    for line in ls.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].startswith("refs/heads/"):
            remote_branches.add(parts[1][len("refs/heads/"):])

    prs = {}
    gh = run(["gh", "pr", "list", "--state", "all", "--limit", "200",
              "--json", "number,state,url,headRefName"], check=False)
    if gh.returncode == 0:
        try:
            for pr in json.loads(gh.stdout or "[]"):
                prs[pr["headRefName"]] = pr
        except (ValueError, KeyError):
            print("warning: could not parse `gh pr list` output - PR checks skipped")
    else:
        print("warning: `gh pr list` failed - PR checks skipped (is gh authenticated?)")

    rows = []
    for iid, item in sorted(items.items()):
        status = item.get("status")
        if status in ("done", "blocked"):
            continue
        if args.epic and item.get("epic") != args.epic:
            continue
        branch = branch_for(item)
        has_branch = branch in remote_branches
        pr = prs.get(branch)
        drift, fix = None, None

        if status in ("in-progress", "changes-requested") and not has_branch and not pr:
            drift = "no branch and no PR on origin - never actually started"
            fix = "ready"
        elif status == "in-review" and pr and pr["state"] == "MERGED":
            drift = f"PR #{pr['number']} is already MERGED"
        elif status == "in-review" and not pr:
            drift = f"no PR found for branch {branch}"
        elif status in ("merged", "qa") and pr and pr["state"] == "OPEN":
            drift = f"PR #{pr['number']} is still OPEN"
        elif status in ("backlog", "ready") and pr and pr["state"] == "OPEN":
            drift = f"not started, but PR #{pr['number']} is open for it"

        if drift:
            rows.append((iid, status, drift, fix))

    if not rows:
        print("OK - every non-terminal item's status matches git/gh reality")
        return 0

    print(f"{len(rows)} item(s) drifted from reality:\n")
    for iid, status, drift, fix in rows:
        arrow = f"--fix resets to {fix}" if fix else "needs a human"
        print(f"  {iid:<12} [{status}]  {drift}")
        print(f"  {'':<12}  -> {arrow}")
    print()

    if not args.fix:
        print("Re-run with --fix to reset the auto-fixable ones.")
        return 1

    fixed = []
    for iid, status, drift, fix in rows:
        if not fix:
            continue
        # in-progress -> ready is not a legal forward transition; this is a
        # correction of a status that was never true, so it forces past it.
        apply_transition(iid, fix, force=True, owner_agent="null")
        fixed.append(iid)
    if fixed:
        _, items = load_all()
        git_commit([rel(items[i]["_path"]) for i in fixed],
                   f"doctor: reset {', '.join(fixed)} to ready (no branch, no PR)")
    unfixed = [r[0] for r in rows if not r[3]]
    if unfixed:
        print(f"\nStill needs a human: {', '.join(unfixed)}")
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_board = sub.add_parser("board")
    p_board.add_argument("--epic")
    p_board.add_argument("--json", action="store_true")
    p_board.set_defaults(func=cmd_board)

    p_ready = sub.add_parser("ready")
    p_ready.add_argument("--epic")
    p_ready.add_argument("--json", action="store_true")
    p_ready.set_defaults(func=cmd_ready)

    p_next = sub.add_parser("next-id")
    p_next.add_argument("prefix")
    p_next.set_defaults(func=cmd_next_id)

    p_set = sub.add_parser("set-status")
    p_set.add_argument("id")
    p_set.add_argument("status")
    p_set.add_argument("--pr-url", dest="pr_url", default=None)
    p_set.add_argument("--attempts", type=int, default=None)
    p_set.add_argument("--owner", default=None)
    p_set.add_argument("--force", action="store_true")
    p_set.set_defaults(func=cmd_set_status)

    p_cyc = sub.add_parser("cycles")
    p_cyc.set_defaults(func=cmd_cycles)

    p_val = sub.add_parser("validate")
    p_val.set_defaults(func=cmd_validate)

    # --- workflow commands ---
    p_start = sub.add_parser("start", help="backlog/ready -> in-progress, committed")
    p_start.add_argument("id")
    p_start.add_argument("--owner", default=None)
    p_start.add_argument("--no-commit", action="store_true")
    p_start.add_argument("--force", action="store_true")
    p_start.set_defaults(func=cmd_start)

    p_open = sub.add_parser("opened", help="-> in-review with a PR URL, committed")
    p_open.add_argument("id")
    p_open.add_argument("--pr-url", dest="pr_url", required=True)
    p_open.add_argument("--no-commit", action="store_true")
    p_open.add_argument("--force", action="store_true")
    p_open.set_defaults(func=cmd_opened)

    p_land = sub.add_parser("land", help="guard, squash-merge, rebase-pull, -> merged, push")
    p_land.add_argument("id")
    p_land.add_argument("--pr-url", dest="pr_url", default=None)
    p_land.add_argument("--no-push", action="store_true")
    p_land.add_argument("--force", action="store_true")
    p_land.set_defaults(func=cmd_land)

    p_fin = sub.add_parser("finish", help="-> qa -> done, commit QA's bug files, push")
    p_fin.add_argument("id")
    p_fin.add_argument("--bug", action="append", default=None,
                       help="repo-relative path to a bug file QA filed; repeatable")
    p_fin.add_argument("--no-push", action="store_true")
    p_fin.add_argument("--force", action="store_true")
    p_fin.set_defaults(func=cmd_finish)

    p_doc = sub.add_parser("doctor", help="reconcile frontmatter against git/gh reality")
    p_doc.add_argument("--epic", default=None)
    p_doc.add_argument("--fix", action="store_true")
    p_doc.set_defaults(func=cmd_doctor)

    args = ap.parse_args()
    try:
        sys.exit(args.func(args))
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
