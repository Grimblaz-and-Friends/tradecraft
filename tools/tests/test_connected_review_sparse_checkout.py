"""Keep every reviewer checkout limited to its independently derived inputs.

The workflow reader supports the block layout used by the shipped template;
unsupported checkout or command forms fail rather than reducing coverage.
Computed resource paths and dynamic imports are outside this static check.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[2]
SHARED = ".github/workflows/connected-review-shared.yml"
TEMPLATE = "skills/connected-review/templates/connected-review.yml"
REFERENCE = "skills/adversarial-review/references/connected-reviewers.md"
SECTION = "## `connected-review.yml` in the repository's GitHub Actions workflows directory"
DESTINATION = ".connected-review-runtime"
JOBS = {"prepare": "eligibility", "review": "review", "report": "report"}


@dataclass
class Checkout:
    source: str
    job: str
    inputs: dict[str, str]
    entrypoints: set[str]
    prompts: set[str]

    @property
    def label(self):
        return f"{self.source}:{self.job}"


def _documented_workflow(reference):
    assert reference.count(SECTION) == 1, f"{REFERENCE}: missing or duplicate template section"
    section = reference.split(SECTION, 1)[1].split("\n## ", 1)[0]
    match = re.search(r"```yaml\n(.*?)\n```", section, re.S)
    assert match, f"{REFERENCE}: missing YAML template block"
    return match[1] + "\n"


def _workflows(root):
    return {
        SHARED: (root / SHARED).read_text(encoding="utf-8"),
        TEMPLATE: (root / TEMPLATE).read_text(encoding="utf-8"),
        REFERENCE: _documented_workflow((root / REFERENCE).read_text(encoding="utf-8")),
    }


def _blocks(lines, pattern, label):
    starts = [(index, re.fullmatch(pattern, line)) for index, line in enumerate(lines)]
    starts = [(index, match) for index, match in starts if match]
    assert starts, f"{label}: unsupported or missing block structure"
    return [
        (match[1], lines[start + 1:end])
        for (start, match), end in zip(starts, [index for index, _ in starts[1:]] + [len(lines)])
    ]


def _checkout_inputs(step, label):
    assert step.count("        with:") == 1, f"{label}: missing or unsupported checkout inputs"
    lines = step[step.index("        with:") + 1:]
    inputs = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if re.match(r"        \S", line):
            break
        match = re.fullmatch(r"          ([a-z][a-z-]*): (.+)", line)
        assert match, f"{label}: unsupported checkout input: {line!r}"
        key, value = match.groups()
        assert key not in inputs, f"{label}: duplicate checkout input {key}"
        index += 1
        if value == "|":
            content = []
            while index < len(lines) and lines[index].startswith("            "):
                content.append(lines[index][12:])
                index += 1
            value = "\n".join(content)
        inputs[key] = value
    return inputs


def _source_path(value, label):
    prefix = DESTINATION + "/"
    assert value.startswith(prefix), f"{label}: unsupported runtime path {value!r}"
    path = value.removeprefix(prefix)
    _canonical_path(path, label)
    return path


def _canonical_path(path, label):
    assert (
        re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", path)
        and all(part not in {".", ".."} for part in path.split("/"))
    ), f"{label}: invalid exact-file path {path!r}"


def _runtime_commands(steps, label, job):
    entrypoints, prompts, commands = set(), set(), []
    for _, body in steps:
        runs = [index for index, line in enumerate(body) if line.startswith("        run:")]
        if not runs:
            assert not any(DESTINATION + "/" in line for line in body), (
                f"{label}: unsupported runtime command structure"
            )
            continue
        assert len(runs) == 1, f"{label}: duplicate run input"
        index = runs[0]
        value = body[index].removeprefix("        run: ")
        if value in {"|", ">-"}:
            content = []
            for line in body[index + 1:]:
                if line.strip() and not line.startswith("          "):
                    break
                content.append(line)
            value = textwrap.dedent("\n".join(content)).strip()
        else:
            assert not any(DESTINATION + "/" in line for line in body[index + 1:]), (
                f"{label}: unsupported runtime command block: {value!r}"
            )
        if DESTINATION + "/" not in value:
            continue
        try:
            tokens = shlex.split(value)
        except ValueError as exc:
            raise AssertionError(f"{label}: unsupported runtime command: {value!r}") from exc
        assert len(tokens) >= 3 and tokens[0] == "python", (
            f"{label}: unsupported runtime command: {value!r}"
        )
        entrypoint = _source_path(tokens[1], label)
        assert entrypoint.endswith(".py"), f"{label}: entrypoint is not Python: {entrypoint}"
        entrypoints.add(entrypoint)
        commands.append(tokens[2])
        if job == "review":
            assert len(tokens) == 5 and tokens[3] == "--finder-prompt", (
                f"{label}: missing or unsupported finder-prompt command: {value!r}"
            )
            prompts.add(_source_path(tokens[4], label))
        else:
            assert len(tokens) == 3, f"{label}: unsupported runtime arguments: {value!r}"
    assert commands == [JOBS[job]], f"{label}: missing or unsupported {JOBS[job]} command"
    return entrypoints, prompts


def _checkouts(workflows):
    checkouts = []
    for source, workflow in workflows.items():
        assert "\t" not in workflow, f"{source}: unsupported tab indentation"
        assert workflow.count("\njobs:\n") == 1, f"{source}: missing or unsupported jobs mapping"
        lines = workflow.split("\njobs:\n", 1)[1].splitlines()
        headers = [line for line in lines if line.strip() and not line.startswith("    ")]
        assert all(re.fullmatch(r"  [a-z][a-z-]*:", line) for line in headers), (
            f"{source}: unsupported job structure"
        )
        jobs = _blocks(lines, r"  ([a-z][a-z-]*):", source)
        assert {job for job, _ in jobs} == set(JOBS) and len(jobs) == len(JOBS), (
            f"{source}: missing, duplicate or unsupported reviewer job"
        )
        for job, body in jobs:
            label = f"{source}:{job}"
            assert body.count("    steps:") == 1, f"{label}: missing or unsupported steps"
            step_lines = body[body.index("    steps:") + 1:]
            assert all(
                not line.strip() or line.startswith("        ")
                or re.fullmatch(r"      - (?:name|uses|id): .+", line)
                for line in step_lines
            ), f"{label}: unsupported step structure"
            steps = _blocks(step_lines, r"      - ((?:name|uses|id): .+)", label)
            entrypoints, prompts = _runtime_commands(steps, label, job)
            found = []
            for first, rest in steps:
                step = ["        " + first, *rest]
                if not any("actions/checkout@" in line for line in step):
                    continue
                uses = [line for line in step if line.startswith("        uses:")]
                assert len(uses) == 1 and re.fullmatch(
                    r"        uses: actions/checkout@[a-zA-Z0-9_.-]+", uses[0]
                ), f"{label}: unsupported checkout action"
                inputs = _checkout_inputs(step, label)
                assert inputs.get("path") == DESTINATION, f"{label}: unsupported checkout destination"
                assert inputs.get("repository") == "${{ env.TRADECRAFT_REPOSITORY }}", (
                    f"{label}: unsupported reviewer repository"
                )
                found.append(Checkout(source, job, inputs, entrypoints, prompts))
            assert found, f"{label}: missing reviewer checkout"
            checkouts.extend(found)
    return checkouts


def _local_module(import_root, parts):
    if not parts:
        candidate = import_root
    else:
        candidate = import_root.joinpath(*parts)
    module = candidate.with_suffix(".py")
    if parts and module.is_file():
        files = {module}
        parent = candidate.parent
    elif candidate.is_dir():
        files = set()
        parent = candidate
    else:
        return set()
    while parent != import_root:
        initializer = parent / "__init__.py"
        if initializer.is_file():
            files.add(initializer)
        parent = parent.parent
    return files


def _import_closure(root, entrypoint):
    entry = root / entrypoint
    assert entry.is_file(), f"missing Python entrypoint: {entrypoint}"
    import_root = entry.parent
    pending, visited = [entry], set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".") for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = []
                if node.level:
                    package = path.parent.relative_to(import_root).parts
                    assert node.level <= len(package), (
                        f"{path.relative_to(root)}: unsupported relative import"
                    )
                    prefix = list(package[:len(package) - node.level + 1])
                parts = prefix + (node.module.split(".") if node.module else [])
                modules.append(parts)
                if import_root.joinpath(*parts).is_dir():
                    modules.extend(parts + [alias.name] for alias in node.names if alias.name != "*")
            for parts in modules:
                pending.extend(_local_module(import_root, parts) - visited)
    return {path.relative_to(root).as_posix() for path in visited}


def _required_files(root, checkout, closures):
    required = set(checkout.prompts)
    for entrypoint in checkout.entrypoints:
        assert (root / entrypoint).is_file(), f"{checkout.label}: missing required file {entrypoint}"
        if entrypoint not in closures:
            closures[entrypoint] = _import_closure(root, entrypoint)
        required.update(closures[entrypoint])
    for path in required:
        assert (root / path).is_file(), f"{checkout.label}: missing required file {path}"
    return required


def _validate(root, workflows):
    checkouts = _checkouts(workflows)
    closures = {}
    required = set().union(*(_required_files(root, checkout, closures) for checkout in checkouts))
    expected = sorted(required)
    for checkout in checkouts:
        label, inputs = checkout.label, checkout.inputs
        assert inputs.get("sparse-checkout-cone-mode") == "false", (
            f"{label}: cone mode must be explicitly false"
        )
        assert "filter" not in inputs, f"{label}: checkout filter overrides sparse fetch"
        assert "sparse-checkout" in inputs, f"{label}: missing sparse-checkout list"
        paths = inputs["sparse-checkout"].splitlines()
        assert len(paths) == len(set(paths)), f"{label}: duplicate sparse path"
        for path in paths:
            _canonical_path(path, label)
            assert (root / path).is_file(), f"{label}: not an existing file: {path}"
        missing, extra = required - set(paths), set(paths) - required
        assert not missing and not extra, (
            f"{label}: missing={sorted(missing)}, extra={sorted(extra)}"
        )
        assert paths == expected, f"{label}: noncanonical sparse ordering: {paths}"
    return checkouts, required


def _set_lists(workflows, required):
    block = "          sparse-checkout: |\n" + "".join(
        f"            {path}\n" for path in sorted(required)
    )
    return {
        source: re.sub(r"          sparse-checkout: \|\n(?:            [^\n]*\n)+", block, workflow)
        for source, workflow in workflows.items()
    }


@pytest.fixture
def reviewer_fixture(tmp_path):
    workflows = _workflows(ROOT)
    _, required = _validate(ROOT, workflows)
    for path in required:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / path).read_bytes())
    return tmp_path, workflows, required


def test_every_reviewer_checkout_matches_derived_dependencies():
    checkouts, _ = _validate(ROOT, _workflows(ROOT))
    assert len(checkouts) == 9


@pytest.mark.parametrize("transitive", [False, True], ids=["direct", "transitive"])
def test_new_local_import_fails_until_every_list_is_updated(reviewer_fixture, transitive):
    root, workflows, required = reviewer_fixture
    source = root / ("lib/vendor_cli.py" if transitive else "lib/connected_review.py")
    # A nested import is just as necessary as one at module scope.
    source.write_bytes(source.read_bytes() + b"\ndef new_feature():\n    import reviewer_extra\n")
    (root / "lib/reviewer_extra.py").write_bytes(b"import pathlib\n")
    with pytest.raises(AssertionError, match=r"missing=.*lib/reviewer_extra.py"):
        _validate(root, workflows)
    _, derived = _validate(root, _set_lists(workflows, required | {"lib/reviewer_extra.py"}))
    assert derived == required | {"lib/reviewer_extra.py"}


def test_package_and_relative_imports_join_the_dependency_closure(reviewer_fixture):
    root, workflows, required = reviewer_fixture
    source = root / "lib/connected_review.py"
    source.write_bytes(source.read_bytes() + b"\nfrom reviewer_package import child\n")
    package = root / "lib/reviewer_package"
    package.mkdir()
    (package / "__init__.py").write_bytes(b"from . import sibling\n")
    (package / "child.py").write_bytes(b"from .sibling import value\n")
    (package / "sibling.py").write_bytes(b"value = 1\n")
    additions = {f"lib/reviewer_package/{name}.py" for name in ("__init__", "child", "sibling")}
    with pytest.raises(AssertionError, match="missing=.*reviewer_package"):
        _validate(root, workflows)
    _, derived = _validate(root, _set_lists(workflows, required | additions))
    assert derived == required | additions


def test_named_prompt_fails_until_every_list_is_updated(reviewer_fixture):
    root, workflows, required = reviewer_fixture
    original = next(path for path in required if path.endswith("finder.md"))
    addition = str(PurePosixPath(original).with_name("new-finder.md"))
    (root / addition).write_bytes(b"A different finder input.\n")
    workflows = {source: workflow.replace(f'{original}"', f'{addition}"')
                 for source, workflow in workflows.items()}
    with pytest.raises(AssertionError, match=r"missing=.*new-finder.md"):
        _validate(root, workflows)
    _validate(root, _set_lists(workflows, (required - {original}) | {addition}))


@pytest.mark.parametrize("source", [SHARED, TEMPLATE, REFERENCE])
@pytest.mark.parametrize("job", JOBS)
def test_each_checkout_discrepancy_is_rejected(reviewer_fixture, source, job):
    root, workflows, _ = reviewer_fixture
    before, body = workflows[source].split(f"  {job}:\n", 1)
    workflows[source] = before + f"  {job}:\n" + body.replace("            lib/winio.py\n", "", 1)
    with pytest.raises(AssertionError, match=re.escape(f"{source}:{job}") + ": missing=.*winio.py"):
        _validate(root, workflows)


@pytest.mark.parametrize("replacement", ["", "          sparse-checkout-cone-mode: true\n"])
@pytest.mark.parametrize("job", JOBS)
def test_omitted_or_enabled_cone_mode_is_rejected(reviewer_fixture, replacement, job):
    root, workflows, _ = reviewer_fixture
    before, body = workflows[TEMPLATE].split(f"  {job}:\n", 1)
    workflows[TEMPLATE] = before + f"  {job}:\n" + body.replace(
        "          sparse-checkout-cone-mode: false\n", replacement, 1,
    )
    with pytest.raises(AssertionError, match=f"{job}: cone mode must be explicitly false"):
        _validate(root, workflows)


@pytest.mark.parametrize("path", [
    "lib", "skills/connected-review/references", "lib/*", "!lib/winio.py",
    "/lib/winio.py", "./lib/winio.py", "lib/../lib/winio.py", "lib\\winio.py",
    "lib/missing.py",
])
def test_invalid_sparse_entry_is_rejected(reviewer_fixture, path):
    root, workflows, _ = reviewer_fixture
    workflows[TEMPLATE] = workflows[TEMPLATE].replace("            lib/winio.py", f"            {path}", 1)
    with pytest.raises(AssertionError, match="invalid exact-file path|not an existing file"):
        _validate(root, workflows)


def test_agreeing_lists_cannot_include_an_unrelated_file(reviewer_fixture):
    root, workflows, required = reviewer_fixture
    (root / "lib/unrelated.py").write_bytes(b"# Not imported by the reviewer.\n")
    with pytest.raises(AssertionError, match=r"extra=.*lib/unrelated.py"):
        _validate(root, _set_lists(workflows, required | {"lib/unrelated.py"}))


@pytest.mark.parametrize("mutation,reason", [
    (lambda text: text.replace("            lib/winio.py\n", "            lib/winio.py\n" * 2, 1), "duplicate sparse path"),
    (lambda text: text.replace("            lib/vendor_cli.py\n            lib/winio.py\n",
                              "            lib/winio.py\n            lib/vendor_cli.py\n", 1), "noncanonical sparse ordering"),
    (lambda text: text.replace("          sparse-checkout: |\n", "          filter: blob:none\n          sparse-checkout: |\n", 1), "filter overrides"),
    (lambda text: re.sub(r"          sparse-checkout: \|\n(?:            [^\n]*\n)+", "", text, count=1), "missing sparse-checkout list"),
])
def test_list_contract_regressions_fail_for_their_cause(reviewer_fixture, mutation, reason):
    root, workflows, _ = reviewer_fixture
    workflows[TEMPLATE] = mutation(workflows[TEMPLATE])
    with pytest.raises(AssertionError, match=reason):
        _validate(root, workflows)


@pytest.mark.parametrize("mutation,reason", [
    (lambda text: text.replace("  report:\n", "  renamed:\n"), "reviewer job"),
    (lambda text: text.replace("      - name: Fetch trusted reviewer\n", "      - {name: Fetch trusted reviewer}\n", 1), "step structure"),
    (lambda text: text.replace("        uses: actions/checkout@", "        uses: 'actions/checkout@", 1), "checkout action"),
    (lambda text: text.replace("        with:\n", "        with: {}\n", 1), "checkout inputs"),
    (lambda text: text.replace("          path: .connected-review-runtime", "          path: elsewhere", 1), "checkout destination"),
    (lambda text: text.replace("        run: python .connected-review-runtime/", "        run: python -u .connected-review-runtime/", 1), "runtime path"),
    (lambda text: text.replace("--finder-prompt", "--finder-prompt="), "finder-prompt command"),
    (lambda text: text.replace("        run: >-", "        run: >"), "runtime command"),
    (lambda text: text.replace("        run: python .connected-review-runtime/lib/connected_review.py eligibility",
                              "        run: echo no-eligibility"), "eligibility command"),
    (lambda text: re.sub(r"      - name: Fetch trusted reviewer\n.*?(?=      - name:)", "", text, count=1, flags=re.S), "missing reviewer checkout"),
])
def test_unsupported_extraction_fails_visibly(reviewer_fixture, mutation, reason):
    root, workflows, _ = reviewer_fixture
    workflows[TEMPLATE] = mutation(workflows[TEMPLATE])
    with pytest.raises(AssertionError, match=reason):
        _validate(root, workflows)


def _run(args, cwd, env):
    return subprocess.run(
        args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding="utf-8", errors="replace", check=True,
    )


@pytest.mark.parametrize("source", [SHARED, TEMPLATE, REFERENCE])
def test_noncone_checkout_materializes_only_runtime_and_runs_commands(tmp_path, source):
    checkouts, required = _validate(ROOT, _workflows(ROOT))
    selected = [checkout for checkout in checkouts if checkout.source == source]
    repository = tmp_path / "source"
    repository.mkdir()
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GIT_") and key.upper() != "PYTHONPATH"}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, PYTHONDONTWRITEBYTECODE="1")
    _run(["git", "init", "--initial-branch=fixture", str(repository)], tmp_path, env)
    # All fixture configuration stays local; no runner setting is changed.
    for key, value in (("user.name", "Sparse fixture"), ("user.email", "fixture@example.invalid"),
                       ("commit.gpgsign", "false"), ("core.autocrlf", "false"),
                       ("core.hooksPath", ".git/no-hooks")):
        _run(["git", "config", "--local", key, value], repository, env)
    for path in required:
        target = repository / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / path).read_bytes())
    for path in ("unrelated.txt", "lib/tests/unrelated.py",
                 "skills/connected-review/references/unrelated.md"):
        target = repository / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"Unrelated fixture: must never materialize.\n")
    _run(["git", "add", "."], repository, env)
    _run(["git", "commit", "-m", "Disposable reviewer sparse fixture"], repository, env)
    sparse = tmp_path / DESTINATION
    _run(["git", "clone", "--no-checkout", str(repository), str(sparse)], tmp_path, env)
    patterns = selected[0].inputs["sparse-checkout"]
    # Match sparseCheckoutNonConeMode() in the pinned checkout action:
    # https://github.com/actions/checkout/blob/fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09/src/git-command-manager.ts
    _run(["git", "config", "core.sparseCheckout", "true"], sparse, env)
    git_path = _run(["git", "rev-parse", "--git-path", "info/sparse-checkout"], sparse, env).stdout.strip()
    (sparse / git_path).write_bytes(f"\n{patterns}\n".encode("utf-8"))
    _run(["git", "checkout", "--progress", "--force", "fixture"], sparse, env)
    materialized = {
        path.relative_to(sparse).as_posix() for path in sparse.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(sparse).parts
    }
    assert materialized == required
    for checkout in selected:
        for entrypoint in checkout.entrypoints:
            result = _run([sys.executable, "-B", str(sparse / entrypoint), JOBS[checkout.job], "--help"], sparse, env)
            assert "usage:" in result.stdout and JOBS[checkout.job] in result.stdout
        for prompt in checkout.prompts:
            result = _run([sys.executable, "-B", "-c",
                           "from pathlib import Path; import sys; "
                           "assert Path(sys.argv[1]).read_bytes()", prompt], sparse, env)
            assert result.returncode == 0
    assert not list(sparse.rglob("__pycache__"))
