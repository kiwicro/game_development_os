#!/usr/bin/env python3
"""
Game Development OS — task board helper.

Deterministic reader/writer for the frontmatter in tasks/epics/*.md,
tasks/tickets/*.md, tasks/bugs/*.md. Skills and agents should shell out to
this instead of hand-parsing YAML — it's the single place that knows the
schema and the status machine defined in CLAUDE.md.

No third-party dependencies (stdlib only), so it runs anywhere Python 3.8+
is available, independent of whatever engine/language the game itself uses.

Commands:
  board [--epic EPIC-ID] [--json]     Render current status.
  ready --epic EPIC-ID [--json]       List ticket/bug IDs eligible to start now.
  next-id <EPIC|TICKET|BUG>           Print the next free ID for that prefix.
  set-status <ID> <new-status>        Update a ticket/bug/epic's status, validating
                                       the transition against the state machine.
                                       [--pr-url URL] [--attempts N] [--owner NAME]
                                       [--force]  (bypass transition validation)
  cycles                              Report dependency cycles among tickets/bugs.
  validate                            Sanity-check the whole tasks/ tree.
"""

import argparse
import json
import re
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

ID_RE = re.compile(r"^(EPIC|TICKET|BUG)-(\d+)-")

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

    items = {}  # tickets + bugs, keyed by id
    for directory in (TICKETS_DIR, BUGS_DIR):
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
    directory = {"EPIC": EPICS_DIR, "TICKET": TICKETS_DIR, "BUG": BUGS_DIR}.get(prefix)
    if directory is None:
        print(f"error: prefix must be EPIC, TICKET, or BUG (got {args.prefix})", file=sys.stderr)
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
    epics, items = load_all()
    target_id = args.id
    is_epic = target_id.startswith("EPIC-")
    store = epics if is_epic else items
    if target_id not in store:
        print(f"error: unknown id {target_id}", file=sys.stderr)
        return 1
    item = store[target_id]
    current = item.get("status")
    new_status = args.status

    valid_statuses = EPIC_STATUSES if is_epic else TICKET_STATUSES
    if new_status not in valid_statuses:
        print(f"error: '{new_status}' is not a valid status for {'an epic' if is_epic else 'a ticket/bug'}", file=sys.stderr)
        return 1

    if not args.force:
        if is_epic:
            allowed = EPIC_TRANSITIONS.get(current, set())
        else:
            allowed = TICKET_TRANSITIONS.get(current, set()) | ({"blocked"} if new_status == "blocked" else set())
        if new_status != current and new_status not in allowed:
            print(
                f"error: {target_id} cannot move {current} -> {new_status} "
                f"(allowed: {sorted(allowed) or '(none)'}). Use --force to override.",
                file=sys.stderr,
            )
            return 1

    set_frontmatter_field(item["_path"], "status", new_status)
    if args.pr_url is not None:
        set_frontmatter_field(item["_path"], "pr_url", args.pr_url)
    if args.attempts is not None:
        set_frontmatter_field(item["_path"], "attempts", args.attempts)
    if args.owner is not None:
        set_frontmatter_field(item["_path"], "owner_agent", args.owner)

    print(f"{target_id}: {current} -> {new_status}")
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

    for iid, item in items.items():
        expected_prefix = "BUG" if item["_path"].parent == BUGS_DIR else "TICKET"
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

    if args.json:
        out = {"epics": {}, "design_docs": {}}
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
                        "ready": is_ready(i, epics, items),
                        "blocked_reason": blocked_reason(i, epics, items) if not is_ready(i, epics, items) else None,
                        "pr_url": i.get("pr_url"),
                    }
                    for iid, i in items.items() if i.get("epic") == eid
                },
            }
        print(json.dumps(out, indent=2))
        return 0

    print("=== Game Development OS — Board ===\n")

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
        done_n = sum(1 for i in eitems if i.get("status") == "done")
        print(f"  {eid:<10} {epic.get('title', ''):<28} [{epic.get('status'):<11}] {done_n}/{len(eitems)} done")
    print()

    for eid, epic in sorted(epics.items()):
        if epic_filter and eid != epic_filter:
            continue
        eitems = sorted((i for i in items.values() if i.get("epic") == eid), key=lambda i: i["id"])
        print(f"{eid} — {epic.get('title', '')} [{epic.get('status')}]")
        if not eitems:
            print("  (no tickets yet)")
        for i in eitems:
            ready = is_ready(i, epics, items)
            tag = "ready-to-start" if ready else (blocked_reason(i, epics, items) or "")
            marker = f"  <- {tag}" if ready else (f"  ({tag})" if tag else "")
            print(f"  {i['id']:<10} [{i.get('status'):<18}] {i.get('title', ''):<32}{marker}")
        print()

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

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
