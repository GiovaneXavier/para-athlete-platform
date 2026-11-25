"""The current engine is still the default: nothing outside the rule book imports the rule book (ADR 0020, step 0 to 2).

When the engines are switched, in a later step the architecture session will ask for, this file changes on purpose.
"""
import ast
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "para_triage"
RULEBOOK = PACKAGE / "rulebook"


def imports_rulebook(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = ("." * node.level) + (node.module or "")
            names = [alias.name for alias in node.names]
            if "rulebook" in module.split(".") or (node.module in (None, "") and "rulebook" in names) or any(n == "rulebook" for n in names):
                found.append(module or "." + ",".join(names))
        elif isinstance(node, ast.Import):
            found += [alias.name for alias in node.names if "rulebook" in alias.name.split(".")]
    return found


def test_no_module_of_the_package_outside_the_rulebook_imports_it():
    offenders = {
        str(p.relative_to(PACKAGE)): found
        for p in PACKAGE.rglob("*.py")
        if RULEBOOK not in p.parents and (found := imports_rulebook(p))
    }
    assert not offenders, offenders


def test_the_scan_would_catch_an_import(tmp_path):
    for code in ("from para_triage.rulebook import Rulebook", "from ..rulebook.interpreter import Rulebook", "from .. import rulebook", "import para_triage.rulebook"):
        sample = tmp_path / "x.py"
        sample.write_text(code + "\n", encoding="utf-8")
        assert imports_rulebook(sample), code
    sample.write_text("from para_triage.rules import RuleEngine\n", encoding="utf-8")
    assert imports_rulebook(sample) == []


def test_no_route_of_the_api_comes_from_the_rule_book():
    pytest.importorskip("fastapi")
    from para_triage.api.app import create_app

    document = create_app().openapi()
    assert not any("rulebook" in path for path in document["paths"])
    assert "rulebook" not in str(document).lower()


def test_the_web_and_the_scripts_do_not_reference_the_rule_book():
    for base in (ROOT / "web" / "src", ROOT / "web" / "scripts"):
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in {".ts", ".tsx", ".mjs", ".js"}:
                assert "rulebook" not in path.read_text(encoding="utf-8").lower(), path


def test_the_current_engine_is_still_what_the_package_exports_as_the_rule_engine():
    from para_triage.rules import RuleEngine

    assert RuleEngine.__module__ == "para_triage.rules.engine"


def test_the_only_change_in_pyproject_for_the_rule_book_is_the_package_data_of_its_yaml():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["tool"]["setuptools"]["package-data"] == {"para_triage": ["rules/*.yaml"], "para_triage.rulebook": ["data/**/*.yaml"]}
    assert not any("rulebook" in d for d in data["project"]["dependencies"])  # no new dependency


def test_nothing_outside_the_package_names_the_shadow_engine_in_the_source_or_the_web():
    for base, suffixes in ((PACKAGE, {".py"}), (ROOT / "web" / "src", {".ts", ".tsx"}), (ROOT / "web" / "scripts", {".mjs", ".js"})):
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in suffixes and RULEBOOK not in path.parents:
                text = path.read_text(encoding="utf-8")
                assert "ShadowEngine" not in text and "rulebook.engine" not in text, path
