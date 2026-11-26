"""A stand-in product change, the cold reading the entrance would order for it, and what the entrance makes of an account.

A use session runs this from the tree under `python -B`. Each situation builds a small Git repository on
this machine, outside the tree, records what the situation says came before, and builds the reading the
gate orders next as the `cold-reader` stage builds it: its tree, its sealed record and its composed
instructions. It prints the reading tree's folder and the file holding those instructions.

- `first`: a change that adds one small file and edits an older one; no reading yet.
- `reread`: the same change after a recorded first reading with two standing flags, and one later commit.
- `shared-document`: several changed files pointing into one document, a recorded first reading, and a
  later commit that edits only that document.

`judge SITUATION ACCOUNT_FILE` reads an account written for that situation's reading and prints what the
entrance makes of it: the form check's result, each earlier flag's verdict, each flag that stands, each flag
outside the change with its reason, and what the gate orders next.

Each situation lives in its own folder under the system's temporary folder, rebuilt on every run, so
nothing is written in the tree this runs from. No real home or store is read, no socket connects and no
`gh` runs: the process isolates itself as the route fixture does before any practice module loads.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

LIB = Path(__file__).resolve().parents[1]
SITUATIONS = ("first", "reread", "shared-document")
ROOT_NAME = "tradecraft-reading-fixture"
WORK = "o/shop#7"
BRANCH = "change/shop-pricing"
DESIGN = """# Shop design

## Pricing

Prices are computed in whole cents, so a basket's total never drifts by a fraction.

## Inventory

Stock counts are kept per item, in memory, for one shop's day.
"""
INVENTORY = '''"""Stock counts per item.

Design: design/shop.md#inventory
"""

STOCK = {}


def receive(item, count):
    # add count to the stock of item
    STOCK[item] = STOCK.get(item, 0) + count


def remaining(item):
    return STOCK.get(item, 0)
'''
RESERVE = '''

def reserve(item, count):
    """Hold stock for an order, so two orders never sell the same unit."""
    if remaining(item) < count:
        raise ValueError(f"only {remaining(item)} of {item} left")
    STOCK[item] -= count
'''
PRICING = '''"""The price of a basket, in whole cents.

Design: design/shop.md#pricing
"""

LOYALTY_DISCOUNT = 0.17


def basket_total(cents):
    total = sum(cents)
    return int(total * (1 - LOYALTY_DISCOUNT))
'''
PRICING_LATER = '''"""The price of a basket, in whole cents.

Design: design/shop.md#pricing
"""

LOYALTY_DISCOUNT = 0.17
LOYALTY_LABEL = "loyalty"


def basket_total(cents):
    total = sum(cents)
    # Rounded down: the shop's terms promise a discount never charges a fraction of a cent over its rate.
    return int(total * (1 - LOYALTY_DISCOUNT))
'''
DASH = chr(0x2014)
REREAD_FIRST = f"""## Sections
shop/pricing.py:1-11 {DASH} prices a basket in whole cents after the loyalty discount; the pointer names design/shop.md#pricing, which says why cents are whole.
shop/inventory.py:18-23 {DASH} reserves stock for an order; its docstring says why.

## Flags
shop/pricing.py:6 {DASH} changeable-number {DASH} the 0.17 discount carries no reason a reader can find
shop/pricing.py:11 {DASH} missing-reason {DASH} nothing says why the total is rounded down rather than to the nearest cent

## Why this change was made
Can tell: yes
The pointed section and the reserve docstring say why.

## Worth a look
shop/inventory.py:19 {DASH} a docstring that gives the reason, not the mechanism.
"""
LEDGER_FILES = ("ledger/accounts.py", "ledger/entries.py", "ledger/periods.py", "ledger/totals.py")
LEDGER_DESIGN = """# Ledger design

## Ledger

Every amount is kept in whole cents.
Entries are append-only, so a period's total can be recomputed from its entries.
"""
LEDGER_DESIGN_CHANGED = LEDGER_DESIGN + "A period closes once its total is posted, so a late entry opens the next.\n"
LEDGER_DESIGN_LATER = (LEDGER_DESIGN_CHANGED + "\nDecisions in force: the ledger keeps one currency per book.\n"
                       "A book's currency is fixed when the book opens.\n")
SHARED_FIRST = f"""## Sections
ledger/accounts.py:1-4 {DASH} names the ledger's accounts; its pointer reaches design/shop.md#ledger.
design/shop.md:7 {DASH} says why a late entry opens the next period.

## Flags
design/shop.md:7 {DASH} in-force-missing {DASH} the section lists no decision in force for the currency the four modules assume

## Why this change was made
Can tell: yes
The pointed section says why.

## Worth a look
design/shop.md:7 {DASH} a reason given in one sentence.
"""


def _git(root: Path, *words: str) -> str:
    environment = {**os.environ, "GIT_AUTHOR_NAME": "Builder", "GIT_AUTHOR_EMAIL": "builder@example.invalid",
                   "GIT_COMMITTER_NAME": "Builder", "GIT_COMMITTER_EMAIL": "builder@example.invalid"}
    return subprocess.run(["git", "-C", str(root), *words], capture_output=True, text=True, env=environment,
                          stdin=subprocess.DEVNULL, check=True).stdout.strip()


def _commit(root: Path, files: dict[str, str], message: str) -> str:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    _git(root, "add", "--all")
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _folder(situation: str) -> Path:
    # Named before isolation moves the temporary folder, so `judge` finds what a situation's run built.
    return Path(tempfile.gettempdir()).resolve() / ROOT_NAME / situation


def _remove(path: Path) -> None:
    def writable(function, name, _error):
        os.chmod(name, stat.S_IWRITE)
        function(name)
    if path.exists():
        shutil.rmtree(path, onexc=writable)


def _isolate(base: Path) -> None:
    sys.path.insert(0, str(LIB / "tests"))
    sys.path.insert(0, str(LIB))
    from route_fixture import isolate
    isolate(base)


class Situation:
    """One situation's repository, records and readings, kept in its folder between `SITUATION` and `judge`."""

    def __init__(self, folder: Path):
        import cold_reader
        self.cold_reader = cold_reader
        self.folder = folder
        self.root, self.home, self.trees = folder / "product", folder / "entrance", folder / "readings"
        self.state_file = folder / "situation.json"
        self.readings: list[dict] = []
        self.base = ""

    def save(self) -> None:
        self.state_file.write_text(json.dumps({"base": self.base, "readings": self.readings}, indent=2),
                                   encoding="utf-8", newline="\n")

    def load(self) -> None:
        value = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.base, self.readings = value["base"], value["readings"]

    def head(self) -> str:
        return _git(self.root, "rev-parse", "HEAD")

    def records(self) -> list[dict]:
        """Each recorded reading as the gate holds it: its sealed record, account and flags."""
        found = []
        for entry in self.readings:
            if entry.get("account") is None:
                continue
            record = self.cold_reader.load_metadata(self.cold_reader.reading_record(Path(entry["tree"]), self.home))
            account = self.cold_reader.parse_account(entry["account"], self.cold_reader.mode_of(record))
            found.append({"id": entry["name"], "record": record, "coverage": record["coverage"],
                          "head": record["head"], "account": account, "accepted": {},
                          "flags": self.cold_reader.reading_flags(record, account)})
        return found

    def assessment(self, readings: list[dict]) -> dict:
        present = self.cold_reader.current(self.root, self.base, self.head())
        return self.cold_reader.assess(readings, present, self.root)

    def read(self, name: str, account: str | None = None) -> Path:
        """Build the reading the gate orders now, as the stage builds it, and write its instructions."""
        order = self.assessment(self.records())["order"]
        if order is None:
            raise SystemExit("reading_fixture: the gate orders no reading here")
        tree = self.trees / name
        record = self.cold_reader.build_tree(
            source=self.root, output=tree, work=WORK, producer_version="fixture", base_tip=self.base,
            head=self.head(), covered=order["covered"], branch=BRANCH, numbers=[7], records_home=self.home,
            order=order)
        metadata = self.cold_reader.load_metadata(record)
        standard = (LIB.parent / "skills" / "authoring" / "references" / "code-reasons.md").read_text("utf-8")
        diff = (record.with_suffix(".diff").read_text("utf-8", errors="replace")
                if metadata["diff"] == "inline" else None)
        excerpts = (self.cold_reader.reading_excerpts(self.root, metadata)
                    if metadata.get("excerpts") == "inline" else None)
        instructions = self.folder / f"{name}-instructions.md"
        instructions.write_bytes(self.cold_reader.compose_prompt(metadata, standard, diff, excerpts))
        self.readings.append({"name": name, "tree": str(tree), "instructions": str(instructions),
                              "account": account})
        self.save()
        return instructions


def build(situation: str) -> int:
    folder = _folder(situation)
    _remove(folder)
    folder.mkdir(parents=True)
    _isolate(folder)
    place = Situation(folder)
    place.root.mkdir()
    _git(place.root, "init", "-q", "-b", "main")
    _git(place.root, "config", "core.autocrlf", "false")
    if situation == "shared-document":
        pointing = {name: f'"""{Path(name).stem.title()} of the ledger.\n\nDesign: design/shop.md#ledger\n"""\n'
                    for name in LEDGER_FILES}
        place.base = _commit(place.root, {"design/shop.md": LEDGER_DESIGN, "README.md": "# Ledger\n"}, "base")
        _git(place.root, "checkout", "-q", "-b", "change")
        _commit(place.root, {**pointing, "design/shop.md": LEDGER_DESIGN_CHANGED}, "the ledger's modules")
        place.read("reading-1", SHARED_FIRST)
        _commit(place.root, {"design/shop.md": LEDGER_DESIGN_LATER}, "the decision the modules assume")
    else:
        place.base = _commit(place.root, {"design/shop.md": DESIGN, "shop/inventory.py": INVENTORY}, "base")
        _git(place.root, "checkout", "-q", "-b", "change")
        _commit(place.root, {"shop/pricing.py": PRICING, "shop/inventory.py": INVENTORY + RESERVE},
                "pricing and reservations")
        if situation == "reread":
            place.read("reading-1", REREAD_FIRST)
            _commit(place.root, {"shop/pricing.py": PRICING_LATER}, "repair")
    name = f"reading-{len(place.readings) + 1}"
    instructions = place.read(name)
    print(f"reading tree: {place.trees / name}")
    print(f"instructions: {instructions}")
    return 0


def judge(situation: str, account_file: Path) -> int:
    folder = _folder(situation)
    if not (folder / "situation.json").is_file():
        print(f"reading_fixture: run `{situation}` first; it builds the reading this judges", file=sys.stderr)
        return 2
    text = account_file.read_text(encoding="utf-8")
    scratch = Path(tempfile.mkdtemp(prefix="judge-", dir=folder))
    _isolate(scratch)
    place = Situation(folder)
    place.load()
    cold_reader = place.cold_reader
    latest = place.readings[-1]
    record = cold_reader.load_metadata(cold_reader.reading_record(Path(latest["tree"]), place.home))
    errors = cold_reader.account_errors(record, text)
    print(f"situation: {situation}; reading: {latest['name']} ({cold_reader.mode_of(record)})")
    if errors:
        print("form check: refused, so this is not a reading and the gate would run it again")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("form check: passes")
    account = cold_reader.parse_account(text, cold_reader.mode_of(record))
    reading = {"id": latest["name"], "record": record, "coverage": record["coverage"], "head": record["head"],
               "account": account, "accepted": {}, "flags": cold_reader.reading_flags(record, account)}
    earlier = {flag["id"]: flag for flag in record.get("earlier_flags") or []}
    print("earlier flags:" + ("" if earlier else " none"))
    for flag_id, flag in earlier.items():
        verdict = account["verdicts"][flag_id]
        print(f"  - {cold_reader.earlier_line(flag)}\n    verdict: {verdict['verdict']}"
              + (f" ({verdict['why']})" if verdict["why"] else ""))
    placed = cold_reader.placement(reading, cold_reader.record_lines(place.root, reading, {}))
    standing = [flag for flag, entry in zip(reading["flags"], placed) if entry["stands"]]
    print("flags that stand:" + ("" if standing else " none"))
    for flag in standing:
        print(f"  - {cold_reader.flag_line(flag)}" + ("  (carried: not answered)" if "carries" in flag else ""))
    outside = [(flag, entry["reason"]) for flag, entry in zip(reading["flags"], placed) if not entry["stands"]]
    print("flags outside the change, needing nothing:" + ("" if outside else " none"))
    for flag, reason in outside:
        print(f"  - {cold_reader.flag_line(flag)}  ({reason})")
    readings = [*place.records(), reading]
    assessment = place.assessment(readings)
    order = assessment["order"]
    if assessment["standing_no"]:
        print("next: a `Can tell: no` stands, so the gate orders a why-check of the whole change")
    elif order is None:
        print("next: nothing stands and no line is unread, so the gate asks for the reading to be posted "
              "and then for `clean`")
    else:
        print(f"next: once the reading is posted, each standing flag is fixed or accepted; the gate then orders "
              f"a {order['mode']} covering {', '.join(order['covered']) or 'no path'}, which judges these flags:")
        for flag in order.get("earlier_flags") or []:
            print(f"  - {cold_reader.flag_line(flag)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(LIB))
    from winio import utf8_stdio
    utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--list", action="store_true", help="name the situations")
    parser.add_argument("words", nargs="*", help="SITUATION, or judge SITUATION ACCOUNT_FILE")
    arguments = parser.parse_args(argv)
    if arguments.list:
        print("\n".join(SITUATIONS))
        return 0
    words = arguments.words
    if len(words) == 1 and words[0] in SITUATIONS:
        return build(words[0])
    if len(words) == 3 and words[0] == "judge" and words[1] in SITUATIONS:
        return judge(words[1], Path(words[2]))
    parser.error("give --list, a situation, or judge SITUATION ACCOUNT_FILE")
    return 2


if __name__ == "__main__":
    sys.exit(main())
