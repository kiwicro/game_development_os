#!/usr/bin/env bash
# Exercises the new workflow subcommands against a throwaway git repo.
# No network: `land` is tested up to and including the tasks/ guard, which is
# the part that runs before any gh call.
set -u

# Usage: bash .claude/scripts/tests/test_workflow.sh
# Builds a throwaway repo in a temp dir; touches nothing in this one.
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/../gdo_board.py"
R="$(mktemp -d)/testrepo"
trap 'rm -rf "$(dirname "$R")" 2>/dev/null' EXIT

mkdir -p "$R/.claude/scripts" "$R/tasks/epics" "$R/tasks/tickets" "$R/tasks/bugs" "$R/tasks/art"
cp "$SRC" "$R/.claude/scripts/gdo_board.py"
B="python .claude/scripts/gdo_board.py"

cat > "$R/tasks/epics/EPIC-001-core.md" <<'EOF'
---
id: EPIC-001
title: Core loop
status: ready
created: 2026-08-24
---
Pitch.
EOF

mk_ticket () {
cat > "$R/tasks/tickets/TICKET-00$1-$2.md" <<EOF
---
id: TICKET-00$1
epic: EPIC-001
title: Ticket $1
status: $3
depends_on: []
attempts: 0
pr_url: null
owner_agent: null
created: 2026-08-24
---

## Acceptance criteria
- does the thing
EOF
}
mk_ticket 1 alpha backlog
mk_ticket 2 beta  backlog
mk_ticket 3 gamma in-review

cd "$R" || exit 1
git init -q -b main 2>/dev/null || { git init -q; git checkout -qb main; }
git config user.email t@t.t; git config user.name t
git add -A >/dev/null; git commit -qm init

pass=0; fail=0
check () { # name expected_rc actual_rc
  if [ "$2" = "$3" ]; then echo "  PASS  $1"; pass=$((pass+1));
  else echo "  FAIL  $1 (expected rc=$2 got rc=$3)"; fail=$((fail+1)); fi
}

echo "--- start ---"
$B start TICKET-001 >/dev/null 2>&1; check "start backlog->in-progress" 0 $?
grep -q "^status: in-progress" tasks/tickets/TICKET-001-alpha.md; check "status written" 0 $?
test -z "$(git status --porcelain)"; check "start committed (clean tree)" 0 $?
git log -1 --pretty=%s | grep -q "TICKET-001: mark in-progress"; check "commit message" 0 $?

$B start TICKET-001 >/dev/null 2>&1; check "start is idempotent" 0 $?
$B start TICKET-003 >/dev/null 2>&1; check "start refuses in-review" 1 $?
$B start TICKET-003 --force >/dev/null 2>&1; check "start --force overrides" 0 $?

echo "--- opened ---"
$B opened TICKET-001 --pr-url https://x/pr/1 >/dev/null 2>&1; check "opened -> in-review" 0 $?
grep -q "^pr_url: https://x/pr/1" tasks/tickets/TICKET-001-alpha.md; check "pr_url recorded" 0 $?
test -z "$(git status --porcelain)"; check "opened committed" 0 $?
$B opened TICKET-002 --pr-url https://x/pr/2 >/dev/null 2>&1; check "opened refuses backlog" 1 $?

echo "--- land guard ---"
# Branch that illegally edits tasks/ - the BUG-002 collision class.
git checkout -qb ticket/TICKET-001-alpha
sed -i 's/^attempts: 0/attempts: 9/' tasks/tickets/TICKET-001-alpha.md
git commit -qam "TICKET-001: sneaky board edit"
git checkout -q main
out=$($B land TICKET-001 2>&1); rc=$?
check "land rejects tasks/-modifying branch" 1 $rc
echo "$out" | grep -q "only gdo_board.py may change board state"; check "guard explains why" 0 $?
echo "$out" | grep -q "TICKET-001-alpha.md"; check "guard names the file" 0 $?
grep -q "^status: in-review" tasks/tickets/TICKET-001-alpha.md; check "guard left status unmutated" 0 $?

echo "--- finish ---"
$B set-status TICKET-001 merged --force >/dev/null 2>&1
cat > tasks/bugs/BUG-001-oops.md <<'EOF'
---
id: BUG-001
epic: EPIC-001
title: Oops
status: backlog
depends_on: []
attempts: 0
pr_url: null
owner_agent: null
created: 2026-08-24
---
repro
EOF
$B finish TICKET-001 --bug tasks/bugs/BUG-001-oops.md --no-push >/dev/null 2>&1
check "finish merged->qa->done" 0 $?
grep -q "^status: done" tasks/tickets/TICKET-001-alpha.md; check "ticket is done" 0 $?
test -z "$(git status --porcelain)"; check "finish committed bug file too" 0 $?
git log -1 --pretty=%s | grep -q "1 bug filed"; check "commit notes the bug" 0 $?
$B finish TICKET-002 --no-push >/dev/null 2>&1; check "finish refuses backlog" 1 $?

echo "--- doctor ---"
$B set-status TICKET-002 ready >/dev/null 2>&1
$B set-status TICKET-002 in-progress >/dev/null 2>&1
git commit -qam "board" >/dev/null 2>&1
out=$($B doctor 2>&1); rc=$?
check "doctor flags drift" 1 $rc
echo "$out" | grep -q "TICKET-002"; check "doctor names the dangling ticket" 0 $?
echo "$out" | grep -q "never actually started"; check "doctor explains drift" 0 $?
$B doctor --fix >/dev/null 2>&1
grep -q "^status: ready" tasks/tickets/TICKET-002-beta.md; check "doctor --fix reset to ready" 0 $?

echo "--- regression: existing commands ---"
$B validate >/dev/null 2>&1; check "validate still passes" 0 $?
$B board --json >/dev/null 2>&1; check "board --json still works" 0 $?
$B next-id TICKET >/dev/null 2>&1; check "next-id still works" 0 $?
$B set-status TICKET-003 done >/dev/null 2>&1; check "set-status still rejects illegal" 1 $?

echo "--- land guard: failure modes ---"
# A branch with no tasks/ edits must pass the guard and reach the gh call.
git checkout -q main
$B set-status TICKET-003 in-review --force >/dev/null 2>&1
git commit -qam wip >/dev/null 2>&1
git checkout -qb ticket/TICKET-003-gamma
echo "code" > game.txt; git add game.txt; git commit -qm "TICKET-003: real code"
git checkout -q main
out=$($B land TICKET-003 --pr-url https://x/pr/3 2>&1); rc=$?
check "clean branch passes guard, fails at gh" 1 $rc
echo "$out" | grep -q "only gdo_board.py"; check "clean branch NOT flagged by guard" 1 $?
echo "$out" | grep -q "gh pr merge"; check "reached the merge step" 0 $?

# An unresolvable branch must hard-error, never silently skip the guard.
$B set-status TICKET-002 in-review --force >/dev/null 2>&1
git commit -qam wip2 >/dev/null 2>&1
out=$($B land TICKET-002 --pr-url https://x/pr/2 2>&1); rc=$?
check "unresolvable branch hard-errors" 1 $rc
echo "$out" | grep -q "guard cannot run"; check "says why the guard could not run" 0 $?
echo "$out" | grep -q "gh pr merge"; check "did NOT reach the merge step" 1 $?


echo "--- qa-queue + batch finish (Phase B) ---"
# Three tickets landed and awaiting QA; one batched pass should clear them
# in a single commit rather than three.
for n in 4 5 6; do
cat > "tasks/tickets/TICKET-00$n-batch$n.md" <<EOF
---
id: TICKET-00$n
epic: EPIC-001
title: Batch $n
status: merged
depends_on: []
attempts: 0
pr_url: https://x/pr/$n
owner_agent: null
created: 2026-08-24
---

## Acceptance criteria
- does thing $n
EOF
done
git add -A >/dev/null; git commit -qm "three merged tickets"

out=$($B qa-queue --epic EPIC-001 2>&1); rc=$?
check "qa-queue succeeds" 0 $rc
echo "$out" | grep -q "3 item(s) awaiting QA"; check "qa-queue counts the merged tickets" 0 $?
echo "$out" | grep -q "TICKET-005"; check "qa-queue lists them" 0 $?
$B qa-queue --epic EPIC-001 --json 2>/dev/null | grep -q '"id": "TICKET-006"'; check "qa-queue --json" 0 $?

before=$(git rev-list --count HEAD)
$B finish TICKET-004 TICKET-005 TICKET-006 --no-push >/dev/null 2>&1
check "batch finish succeeds" 0 $?
after=$(git rev-list --count HEAD)
test "$((after - before))" = "1"; check "batch finish made ONE commit for 3 tickets" 0 $?
grep -q "^status: done" tasks/tickets/TICKET-004-batch4.md; check "batch: 004 done" 0 $?
grep -q "^status: done" tasks/tickets/TICKET-006-batch6.md; check "batch: 006 done" 0 $?
git log -1 --pretty=%s | grep -q "TICKET-004, TICKET-005, TICKET-006"; check "batch commit names all three" 0 $?
$B qa-queue --epic EPIC-001 2>&1 | grep -q "QA queue empty"; check "qa-queue empty after finish" 0 $?

# A bad ID anywhere in the batch must abort before mutating any of them.
cat > "tasks/tickets/TICKET-007-batch7.md" <<'EOF'
---
id: TICKET-007
epic: EPIC-001
title: Batch 7
status: merged
depends_on: []
attempts: 0
pr_url: null
owner_agent: null
created: 2026-08-24
---
x
EOF
git add -A >/dev/null; git commit -qm "one more"
$B finish TICKET-007 TICKET-999 --no-push >/dev/null 2>&1
check "batch finish rejects unknown ID" 1 $?
grep -q "^status: merged" tasks/tickets/TICKET-007-batch7.md; check "batch aborted before mutating anything" 0 $?


echo "--- parallel-batch (Phase C) ---"
rm -f tasks/tickets/TICKET-00*.md tasks/bugs/BUG-001-oops.md
mk_par () { # id slug touches
cat > "tasks/tickets/TICKET-0$1-$2.md" <<EOF
---
id: TICKET-0$1
epic: EPIC-001
title: Par $1
status: ready
depends_on: []
attempts: 0
touches: $3
pr_url: null
owner_agent: null
created: 2026-08-24
---
x
EOF
}
mk_par 10 ui      "[src/ui/]"
mk_par 11 uimenu  "[src/ui/menu.gd]"
mk_par 12 audio   "[src/audio/]"
mk_par 13 nofp    "[]"
git add -A >/dev/null; git commit -qm "parallel fixtures"

out=$($B parallel-batch --epic EPIC-001 2>&1); rc=$?
check "parallel-batch runs" 0 $rc
echo "$out" | grep -q "TICKET-010"; check "picks the first ready item" 0 $?
echo "$out" | grep -q "TICKET-011.*touches overlaps TICKET-010"; check "defers overlapping footprint" 0 $?
echo "$out" | grep -q "TICKET-012"; check "keeps disjoint footprint in batch" 0 $?
echo "$out" | grep -q "NOT mechanically checked"; check "warns about undeclared footprint" 0 $?
echo "$out" | grep -q "TICKET-013"; check "names the unchecked item" 0 $?

$B parallel-batch --epic EPIC-001 --max 1 2>&1 | grep -q "already at --max 1"; check "--max caps the batch" 0 $?
$B parallel-batch --epic EPIC-001 --json 2>/dev/null | grep -q '"no_declared_footprint": \["TICKET-013"\]'; check "parallel-batch --json shape" 0 $?
$B parallel-batch --epic NOPE-999 >/dev/null 2>&1; check "parallel-batch rejects unknown epic" 1 $?
$B validate >/dev/null 2>&1; check "touches: does not break validate" 0 $?


echo
echo "$pass passed, $fail failed"
[ "$fail" = 0 ]
