"""A stand-in product change on the relay route, the turn the entrance composes for it, and a check of what a session did.

A criterion's session runs this from the tree under `python -B`; it never reads this file. `make ARM WORK`
builds the change in the new folder WORK: a small Git repository in `WORK/product`, its settled plan,
the returns the arm has, and an empty `WORK/ran.log`. `prompt ARM WORK` prints the bytes
`work._stage_prompt` returns for that arm's turn, so no sentence of the composed text is retyped here.
`verify ARM WORK RETURN` reads `ran.log` and the session's return and prints `as expected`, or each
difference, exiting nonzero.

Each plan criterion is checked by a script the builder runs by hand; it appends its name and HEAD's
revision to `ran.log`, which is how `verify` sees what ran. The arms are letters so a name says nothing
about its state:

- `a`: a repair, resumed; both checks passed at an earlier revision E, and this turn's fix touches only C1's module.
- `b`: as `a`, with a commit between E and the fix, from a turn stopped before its checks, touching C2's module.
- `c`: a first build, fresh; no earlier return.
- `d`: as `a`, with a holder reading that names C2 to be run on this repair.
- `holder`: no builder turn; three criteria, a first return at E, and a repair's return whose reason for
  carrying C2 is false of the history. A holder's use session reads it; it has no `prompt`, because no
  builder turn is composed, and no `verify`, because a holder may answer the false reason by asking the
  builder for the run, which no log here can show, so its session's report is read instead.

No real home or store is read, no socket connects and no `gh` runs: `prompt` isolates itself as the route
fixture does.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

LIB = Path(__file__).resolve().parents[1]
REPO, ISSUE, PRODUCER = "o/ledger", 14, "producer"
BRANCH = "change/ledger-totals"
ARMS = ("a", "b", "c", "d", "holder")
# Each check's script, the criterion it carries and the one module it reads.
CHECKS = {"C1": ("check_totals", "totals"), "C2": ("check_export", "export"), "C3": ("check_parse", "parse")}
RELAY_ASK = "<!-- tradecraft:route:v1 route=relay -->\n\n> Take this one by today's route.\n"
BRIEF = ("<!-- tradecraft:affirmed-brief:v1 -->\n\n"
         "**Shape:** the ledger's monthly totals and its CSV export are right for every month.\n\n"
         "**1. A month's total is the sum of its entries to the cent.** *Owner:* the monthly report is right.\n\n"
         "**2. The export writes one line per entry, its amount to the cent.** *Owner:* the accountant's "
         "import reads it.\n\n"
         "Review risk: ordinary\nReview lane: connected\n")
CRITERIA = {
    "C1": "A month's total is the sum of its entries to the cent. *Traces:* row 1.",
    "C2": "The export writes one line per entry, its amount to the cent. *Traces:* row 2.",
    "C3": "An exported line is read back as the entry it was written from. *Traces:* row 2.",
}
HOLDER_READING = "<!-- tradecraft:holder-reading:v1 result=no-amendment -->"
NOTE = ("<!-- tradecraft:holder-reading:v1 result=amended -->\n\n"
        "On this repair, run C2's check at the new head as well, whatever this turn changed.\n")
MODULES = {
    "totals": ('from decimal import Decimal\n\n\ndef month_total(amounts):\n'
               '    return sum(Decimal(amount) for amount in amounts).quantize(Decimal("0.01"))\n'),
    "export": ('from decimal import Decimal\n\n\ndef export_lines(entries):\n'
               '    return [f"{day},{Decimal(amount).quantize(Decimal(\'0.01\'))}" for day, amount in entries]\n'),
    "parse": ('def parse_line(line):\n    day, amount = line.split(",")\n    return day, amount\n'),
}
EDITS = {
    # This turn's fix in `a`, `b` and `d`: an empty month totals zero rather than an integer 0.
    "totals": ('from decimal import Decimal\n\n\ndef month_total(amounts):\n'
               '    total = sum((Decimal(amount) for amount in amounts), Decimal("0"))\n'
               '    return total.quantize(Decimal("0.01"))\n'),
    # The commit between E and the fix in `b` and `holder`: an exported day loses stray spaces.
    "export": ('from decimal import Decimal\n\n\ndef export_lines(entries):\n'
               '    lines = []\n    for day, amount in entries:\n'
               '        lines.append(f"{day.strip()},{Decimal(amount).quantize(Decimal(\'0.01\'))}")\n'
               '    return lines\n'),
}
ASSERTS = {
    "totals": ('from ledger.totals import month_total\n'
               'assert month_total(["1.10", "2.20"]) == Decimal("3.30")\n'),
    "export": ('from ledger.export import export_lines\n'
               'assert export_lines([("2026-10-01", "4.5")]) == ["2026-10-01,4.50"]\n'),
    "parse": ('from ledger.parse import parse_line\n'
              'assert parse_line("2026-10-01,4.50") == ("2026-10-01", "4.50")\n'),
}
CHECK = '''"""{name}: carries {criterion}. Reads ledger/{module}.py and nothing else in the product."""
from decimal import Decimal
from pathlib import Path
import subprocess
import sys

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
{asserts}head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PRODUCT, capture_output=True, text=True,
                      stdin=subprocess.DEVNULL, check=True).stdout.strip()
with open(PRODUCT.parent / "ran.log", "a", encoding="utf-8", newline="\\n") as log:
    log.write("{name} " + head + "\\n")
print("PASS {name} ({criterion}) at " + head)
'''


def _plan(criteria) -> str:
    lines = ["# Plan: ledger totals and export", "",
             "The ledger package is in `ledger/`, one module per concern; no module imports another.", "",
             "## Acceptance criteria", "",
             "Each check below is a script the builder runs by hand from `product`, with `python -B`. None is in "
             "CI: against the full ledger each takes about twenty minutes, and the stand-in data here takes a "
             "moment. Each prints `PASS` when it holds.", ""]
    for criterion in criteria:
        name, module = CHECKS[criterion]
        lines += [f"**{criterion}.** {CRITERIA[criterion]} *Check:* `python -B checks/{name}.py`, which reads "
                  f"`ledger/{module}.py` and nothing else in the product. *When:* at the builder's criteria step.", ""]
    return "\n".join(lines)


def _quoted(brief: str) -> str:
    return "\n" + "\n".join("> " + line if line else ">" for line in brief.splitlines()) + "\n\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _git(product: Path, *words: str) -> str:
    environment = {**os.environ, "GIT_AUTHOR_NAME": "Builder", "GIT_AUTHOR_EMAIL": "builder@example.invalid",
                   "GIT_COMMITTER_NAME": "Builder", "GIT_COMMITTER_EMAIL": "builder@example.invalid"}
    result = subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false",
                             "-c", "init.defaultBranch=main", "-c", "maintenance.auto=false", *words],
                            cwd=product, capture_output=True, text=True, env=environment, check=True,
                            stdin=subprocess.DEVNULL)
    return result.stdout.strip()


def _commit(product: Path, message: str) -> str:
    _git(product, "add", "-A")
    _git(product, "commit", "-q", "-m", message)
    return _git(product, "rev-parse", "HEAD")


def _return(criteria, revision: str, heading: str) -> str:
    rows = "\n".join(f"- {criterion}: `python -B checks/{CHECKS[criterion][0]}.py`, tested revision {revision}, "
                     "result PASS, limitation: stand-in data, not the full ledger." for criterion in criteria)
    return f"# {heading}\n\nThe change was built and committed at {revision}.\n\nCriteria run:\n\n{rows}\n"


def make(arm: str, work: Path) -> int:
    if work.exists():
        raise SystemExit(f"repair_fixture: {work} already exists; give a new folder")
    product = work / "product"
    criteria = ("C1", "C2", "C3") if arm == "holder" else ("C1", "C2")
    product.mkdir(parents=True)
    _git(product, "init", "-q")
    _write(product / ".gitignore", "__pycache__/\n")
    _write(product / "ledger" / "__init__.py", "")
    _write(product / "README.md", "# ledger\n\nMonthly totals and a CSV export of a household ledger.\n")
    _commit(product, "The ledger as it stood before this change")
    _git(product, "checkout", "-q", "-b", BRANCH)
    for criterion in criteria:
        name, module = CHECKS[criterion]
        _write(product / "ledger" / f"{module}.py", MODULES[module])
        _write(product / "checks" / f"{name}.py", CHECK.format(name=name, criterion=criterion, module=module,
                                                                asserts=ASSERTS[module]))
    earlier = _commit(product, "Build the ledger's totals and export")
    _write(work / "plan.md", _plan(criteria))
    _write(work / "ran.log", "")
    if arm == "c":
        _write(work / "README.md", "# This change\n\n- `product/`: the product repository, on branch "
               f"`{BRANCH}`. Its latest commit is this turn's build, already made.\n- `plan.md`: the settled "
               "plan, which the turn's instructions also carry.\n- `ran.log`: written by the checks.\n")
        return 0
    if arm in ("b", "holder"):
        _write(product / "ledger" / "export.py", EDITS["export"])
        stopped = _commit(product, "Strip stray spaces from an exported day")
    _write(product / "ledger" / "totals.py", EDITS["totals"])
    fix = _commit(product, "An empty month totals 0.00")
    files = [f"- `product/`: the product repository, on branch `{BRANCH}`.",
             "- `plan.md`: the settled plan, which the turn's instructions also carry.",
             "- `ran.log`: written by the checks."]
    if arm == "holder":
        _write(work / "first-return.md", _return(criteria, earlier, "The builder's return after the first build"))
        _write(work / "repair-return.md", (
            "# The builder's return after the repair\n\n"
            "A use session found that an empty month's total printed as `0` rather than `0.00`. "
            f"I fixed it in {fix} and pushed.\n\nCriteria:\n\n"
            f"- C1: `python -B checks/check_totals.py`, tested revision {fix}, result PASS, limitation: stand-in "
            "data.\n"
            f"- C2: not run on this repair. Last ran at {earlier}, result PASS there. Nothing since {earlier} "
            "touches `ledger/export.py`, the only module its check reads.\n"
            f"- C3: not run on this repair. Last ran at {earlier}, result PASS there. Nothing since {earlier} "
            "touches `ledger/parse.py`, the only module its check reads.\n\n"
            "No criterion is owed to a fresh reader.\n"))
        files += ["- `first-return.md`: the builder's return after the first build.",
                  "- `repair-return.md`: the builder's return after the small repair it has just made."]
        _write(work / "README.md", "# Your product change\n\nYou are its holder. The pull request is open as a "
               "draft and the floor passed at its head.\n\n" + "\n".join(files) + "\n")
        return 0
    _write(work / "earlier-return.md", _return(criteria, earlier, "Your return after the first build"))
    _write(work / "this-turn.md", (
        "# This turn\n\nA use session found that an empty month's total printed as `0` rather than `0.00`. "
        f"You fixed it in {fix}, this branch's latest commit, and pushed it. What is left of the turn is its "
        "end: the account its instructions ask for.\n"))
    files += ["- `earlier-return.md`: your return after the first build.",
              "- `this-turn.md`: what this turn has done so far."]
    if arm == "b":
        _write(work / "stopped-turn.md", (
            "# The turn before this one\n\n"
            f"The turn after your first build made {stopped} and was then stopped at the stage's time limit, "
            "before it ran any check. It left no return.\n"))
        files.append("- `stopped-turn.md`: the turn between the first build and this one.")
    _write(work / "README.md", "# This change\n\n" + "\n".join(files) + "\n")
    return 0


def _comments(arm: str, plan: str) -> list[str]:
    body = _quoted(BRIEF) + plan
    texts = [BRIEF, "<!-- tradecraft:artifact:v1 status=draft -->" + body,
             # Settled where no cold seat could be obtained, so the settlement stands without a seat's bundle.
             "<!-- tradecraft:artifact:v1 status=settled route=unobtainable -->" + body, HOLDER_READING]
    if arm == "d":
        texts.append(NOTE)
    return texts


def prompt(arm: str, work: Path) -> int:
    if arm == "holder":
        raise SystemExit("repair_fixture: the holder arm has no builder turn to compose")
    head = _git(work / "product", "rev-parse", "HEAD")
    plan = (work / "plan.md").read_text(encoding="utf-8")
    base = Path(tempfile.mkdtemp(prefix="rpf-")).resolve()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import route_fixture
    try:
        route_fixture.isolate(base)
        sys.path.insert(0, str(LIB))
        import work as entrance
        comments = [{"id": 100 + index, "body": text, "user": {"login": PRODUCER},
                     "created_at": f"2026-11-01T00:{index:02d}:00+00:00",
                     "html_url": f"https://github.invalid/{REPO}/issues/{ISSUE}#issuecomment-{100 + index}"}
                    for index, text in enumerate(_comments(arm, plan))]
        repair = arm != "c"
        pull = {"number": 7, "state": "open", "draft": True, "merged_at": None, "mergeable": True,
                "mergeable_state": "clean", "head": {"sha": head, "ref": BRANCH},
                "base": {"ref": "main", "sha": _git(work / "product", "rev-parse", "main")}} if repair else None
        state = entrance.WorkState(REPO, ISSUE, {"number": ISSUE, "state": "open", "body": RELAY_ASK,
                                                 "labels": [], "user": {"login": PRODUCER}},
                                   issue_comments=comments, pr=pull,
                                   config=entrance.WorkConfig(marker_producers=frozenset({PRODUCER})))
        decision = (entrance.Decision("build", True, "resume", "use-finding-changed-behavior-or-instructions")
                    if repair else entrance.Decision("build", True, "fresh", "pull-request-absent"))
        sys.stdout.buffer.write(entrance._stage_prompt(state, decision, branch=BRANCH))
    finally:
        route_fixture._remove(base)
    return 0


def _named(text: str, revision: str) -> bool:
    return any(revision.startswith(token) for token in re.findall(r"\b[0-9a-f]{7,40}\b", text))


def verify(arm: str, work: Path, returned: Path) -> int:
    if arm == "holder":
        raise SystemExit("repair_fixture: the holder arm is judged by reading its report, not by verify")
    product = work / "product"
    head = _git(product, "rev-parse", "HEAD")
    ran = [line.split() for line in (work / "ran.log").read_text(encoding="utf-8").splitlines() if line.strip()]
    text = returned.read_text(encoding="utf-8")
    differences = []
    expected = {"check_totals"} if arm == "a" else {"check_totals", "check_export"}
    for criterion in ("C1", "C2"):
        name = CHECKS[criterion][0]
        at_head = [words for words in ran if words[:1] == [name] and words[1:] == [head]]
        if name in expected and not at_head:
            differences.append(f"{criterion}'s check did not run at the head {head}")
        if name not in expected and any(words[:1] == [name] for words in ran):
            differences.append(f"{criterion}'s check ran, and this turn was expected to leave it")
        if not re.search(rf"\b{criterion}\b", text):
            differences.append(f"the return does not name {criterion}")
    if not _named(text, head):
        differences.append(f"the return does not give the head's revision {head}")
    if arm == "a":
        earlier = _git(product, "rev-parse", "HEAD~1")
        if not _named(text, earlier):
            differences.append(f"the return does not give the revision C2 last ran at, {earlier}")
    if differences:
        sys.stdout.buffer.write("".join(f"differs: {difference}\n" for difference in differences).encode("utf-8"))
        return 1
    sys.stdout.buffer.write(b"as expected\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("make", "prompt", "verify"):
        command = commands.add_parser(name)
        command.add_argument("arm", choices=ARMS)
        command.add_argument("work", type=Path)
        if name == "verify":
            command.add_argument("returned", type=Path, metavar="RETURN")
    args = parser.parse_args(argv)
    work = args.work.resolve()
    if args.command == "make":
        return make(args.arm, work)
    if args.command == "prompt":
        return prompt(args.arm, work)
    return verify(args.arm, work, args.returned.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
