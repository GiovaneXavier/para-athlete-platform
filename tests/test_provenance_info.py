import json
import shutil

import pytest

from para_triage.provenance_info import (
    EVIDENCE_LEVEL,
    KNOWN_CHECKPOINTS,
    checkpoint_info,
    file_sha256,
    rules_version,
)
from para_triage.provenance_info import checkpoint as checkpoint_module
from para_triage.provenance_info.rules_version import RULES_DIR


@pytest.fixture()
def rules_copy(tmp_path):
    dest = tmp_path / "rules"
    shutil.copytree(RULES_DIR, dest, ignore=shutil.ignore_patterns("__pycache__"))
    return dest


# --- rules version ---------------------------------------------------------------------------------------


def test_rules_version_is_stable_and_covers_the_catalog_and_every_evaluator():
    first, second = rules_version(), rules_version()
    assert first == second
    assert first.id.startswith("rules-") and first.sha256.startswith(first.id.removeprefix("rules-"))
    names = [name for name, _ in first.files]
    assert names[0] == "classes.yaml"
    assert {"engine.py", "catalog.py", "schema.py"} <= set(names)
    assert {"evaluators/functional.py", "evaluators/limb.py", "evaluators/sensory.py"} <= set(names)


@pytest.mark.parametrize("name", ["engine.py", "catalog.py", "schema.py"])
def test_rules_version_changes_when_the_engine_catalog_or_schema_source_changes(rules_copy, name):
    base = rules_version().id
    source = rules_copy / name
    source.write_text(source.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    assert rules_version(rules_copy).id != base


def test_rules_version_ignores_where_the_files_live_and_their_line_endings(rules_copy):
    assert rules_version(rules_copy) == rules_version()
    catalog = rules_copy / "classes.yaml"
    catalog.write_bytes(catalog.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert rules_version(rules_copy).id == rules_version().id


def test_rules_version_changes_when_a_criterion_or_an_evaluator_changes(rules_copy):
    base = rules_version().id
    catalog = rules_copy / "classes.yaml"
    original = catalog.read_text(encoding="utf-8")
    catalog.write_text(original.replace("logmar_gt: 2.60", "logmar_gt: 2.70"), encoding="utf-8")
    assert rules_version(rules_copy).id != base

    catalog.write_text(original, encoding="utf-8")
    assert rules_version(rules_copy).id == base
    evaluator = rules_copy / "evaluators" / "limb.py"
    evaluator.write_text(evaluator.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    assert rules_version(rules_copy).id != base


def test_rules_version_reports_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        rules_version(tmp_path)


# --- checkpoint ------------------------------------------------------------------------------------------


def write_metrics(folder, agreement=0.9):
    stat = {"mean": agreement, "std": 0.01}
    metrics = {"aggregate": {"overall": {"mlp": {"accuracy": stat, "macro_f1": stat}}}, "runs": [{}, {}, {}]}
    (folder / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")


def test_checkpoint_info_is_none_without_a_file(tmp_path):
    assert checkpoint_info(tmp_path / "model.pt") is None


def test_unknown_checkpoint_gets_a_hash_but_no_borrowed_protocol_or_metrics(tmp_path):
    (tmp_path / "model.pt").write_bytes(b"not a real checkpoint")
    write_metrics(tmp_path)  # a metrics file next to an unregistered checkpoint is not trusted
    info = checkpoint_info(tmp_path / "model.pt")
    assert info.sha256 == file_sha256(tmp_path / "model.pt") and info.size_bytes == 21
    assert not info.known and info.status == "unknown"
    assert info.protocol is None and info.metrics is None and info.limits == ()
    assert info.file_name == "model.pt" and str(tmp_path) not in repr(info)


def test_known_checkpoint_carries_protocol_limits_and_metrics_read_from_disk(tmp_path, monkeypatch):
    (tmp_path / "model.pt").write_bytes(b"known weights")
    write_metrics(tmp_path, agreement=0.9)
    sha = file_sha256(tmp_path / "model.pt")
    monkeypatch.setitem(
        checkpoint_module.KNOWN_CHECKPOINTS,
        sha,
        {"name": "toy", "status": "preliminary", "protocol": "toy protocol", "limits": ("toy limit",)},
    )
    info = checkpoint_info(tmp_path / "model.pt")
    assert info.known and info.name == "toy" and info.status == "preliminary"
    assert info.protocol == "toy protocol" and info.limits == ("toy limit",)
    assert info.metrics["n_runs"] == 3
    assert info.metrics["mlp_agreement_with_rule_labels"] == {"mean": 0.9, "std": 0.01}
    assert info.metrics["evidence_level"] == info.evidence_level == EVIDENCE_LEVEL


def test_known_checkpoint_without_a_readable_metrics_file_has_no_metrics(tmp_path, monkeypatch):
    (tmp_path / "model.pt").write_bytes(b"known weights")
    (tmp_path / "metrics.json").write_text("{broken", encoding="utf-8")
    monkeypatch.setitem(
        checkpoint_module.KNOWN_CHECKPOINTS,
        file_sha256(tmp_path / "model.pt"),
        {"name": "toy", "status": "preliminary", "protocol": "p", "limits": ()},
    )
    assert checkpoint_info(tmp_path / "model.pt").metrics is None


def test_registry_describes_mlp_v1_as_preliminary():
    entries = [e for e in KNOWN_CHECKPOINTS.values() if e["name"] == "mlp_v1"]
    assert len(entries) == 1 and entries[0]["status"] == "preliminary"
    assert not any("acurácia" in text.lower() for text in [entries[0]["protocol"], *entries[0]["limits"]])


def test_rules_version_from_contents_matches_the_files_it_was_read_from():
    from para_triage.provenance_info import rules_version_from_contents

    current = rules_version()
    contents = {name: (RULES_DIR / name).read_bytes() for name, _ in current.files}
    assert rules_version_from_contents(contents) == current
    contents["classes.yaml"] += b"# changed"
    assert rules_version_from_contents(contents).id != current.id


def test_rules_id_at_a_git_commit_matches_the_working_tree_when_the_rules_are_committed():
    import subprocess

    from para_triage.transparency.export import REPO_ROOT, rules_id_at_commit

    try:
        dirty = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--", "src/para_triage/rules"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git is not available")
    if dirty.returncode != 0 or dirty.stdout.strip():
        pytest.skip("not a git checkout, or the rules have uncommitted changes")
    assert rules_id_at_commit("HEAD") == rules_version().id
    assert rules_id_at_commit("0" * 40) is None
