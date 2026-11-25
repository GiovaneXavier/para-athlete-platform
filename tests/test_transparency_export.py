"""The export script of the transparency panel (K11) on a tiny synthetic runs/ folder."""
import json

import pandas as pd
import pytest

from para_triage.transparency import export as ex

CELLS = [(0.0, 0.0), (1.0, 1.0), (1.0, 2.0)]


def write(path, frame):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def config(folder, runs, **extra):
    body = {
        "seeds": [0, 1],
        "split_mode": "row",
        "commit": "0" * 40,  # unknown to git: the rule id at the source commit stays null
        "code_tree_dirty": False,
        "written_at": "2026-10-24T15:37:11-03:00",
        "python": "3.12.10",
        "torch": "2.11.0+cpu",
        "scikit_learn": "1.9.1",
        "command": r"python.exe C:\Users\someone\secret folder\src\para_triage\experiments\e1.py --seeds 0 1 --out runs/e1",
        **extra,
    }
    (runs / folder).mkdir(parents=True, exist_ok=True)
    (runs / folder / "config.json").write_text(json.dumps(body), encoding="utf-8")


def make_e1(runs, folder, mlp_accuracy):
    rows, extras = [], []
    for seed in (0, 1):
        for train in CELLS:
            for test in CELLS:
                keys = dict(seed=seed, train_noise=train[0], train_missing=train[1], test_noise=test[0], test_missing=test[1])
                for system in ("rules", "mlp"):
                    value = 0.5 if system == "rules" else mlp_accuracy[seed]
                    rows.append({**keys, "system": system, "accuracy": value, "macro_f1": value, "coverage": 1.0, "accuracy_decided": value})
                extras.append({**keys, "mlp_top2": 0.9, "mlp_ece": 0.01, "mlp_nll": 0.2, "mlp_brier": 0.1})
    write(runs / folder / "results.csv", pd.DataFrame(rows))
    write(runs / folder / "extras.csv", pd.DataFrame(extras))
    config(folder, runs, n_per_label=300, split={"train": 0.6})


def make_e7(runs, folder):
    marginal, conditional, selective = [], [], []
    for seed in (0, 1):
        for split in (0, 1):
            for method in ex.CONFORMAL_METHODS:
                for alpha in ex.ALPHAS:
                    marginal.append(
                        dict(
                            seed=seed, split=split, model="mlp", method=method, alpha=alpha,
                            cal_noise=1.0, cal_missing=1.0, test_noise=1.0, test_missing=1.0,
                            coverage=0.9 + 0.01 * split, size=1.0, frac_singleton=0.9, frac_decided=0.8, frac_empty=0.02,
                            frac_has_ambiguous=0.1, singleton_accuracy=0.93, decided_accuracy=0.94,
                        )
                    )
            for by, values in (("group", ["visual"]), ("missing_fields", ["0", "1", "2+"])):
                for value in values:
                    conditional.append(
                        dict(by=by, value=value, coverage=0.95 if value == "0" else 0.7, size=1.1, n=100, seed=seed,
                             split=split, model="mlp", method="LAC", alpha=0.1, cell_noise=1.0, cell_missing=1.0)
                    )
        for method in ("mlp_maxprob", "gb_maxprob", "mlp_margin"):
            selective.append(
                dict(seed=seed, method=method, aurc=0.02, rules_coverage=0.86, selective_accuracy_at_rules_coverage=0.95,
                     selective_accuracy_at_50=0.98, selective_accuracy_at_70=0.97, selective_accuracy_at_90=0.94, accuracy_full=0.89)
            )
    write(runs / folder / "marginal.csv", pd.DataFrame(marginal))
    write(runs / folder / "conditional.csv", pd.DataFrame(conditional))
    write(runs / folder / "selective_summary.csv", pd.DataFrame(selective))
    config(folder, runs, declared_before_running={"primary_conformal_score": "LAC"})


def make_v1(runs):
    accuracy, duplicates, grouped, meta = [], [], [], []
    for seed in (0, 1):
        for subset in ("all", "true_duplicate"):
            for system in ("rules", "mlp"):
                accuracy.append(dict(seed=seed, subset=subset, system=system, n=100, accuracy=0.8))
        for group, n in (("visual", 100), ("limb", 300)):
            duplicates.append(dict(seed=seed, group=group, n_test=n, share_true_duplicate=0.5, share_observed_duplicate=0.25))
        for variant in ("profile", "profile_by_label"):
            for system in ("rules", "mlp"):
                grouped.append(dict(seed=seed, variant=variant, system=system, accuracy=0.6, macro_f1=0.6, coverage=1.0, accuracy_decided=0.6))
            meta.append(dict(seed=seed, variant=variant, n_train=800, n_test=200, share_test_label_unseen_in_train=0.2, unique_true_profiles=400))
    write(runs / "v1" / "accuracy.csv", pd.DataFrame(accuracy))
    write(runs / "v1" / "duplicates.csv", pd.DataFrame(duplicates))
    write(runs / "v1" / "grouped_systems.csv", pd.DataFrame(grouped))
    write(runs / "v1" / "grouped_meta.csv", pd.DataFrame(meta))
    config("v1", runs)


@pytest.fixture()
def runs(tmp_path):
    root = tmp_path / "runs"
    make_e1(root, "e1", {0: 0.9, 1: 0.8})
    make_e1(root, "e1_profile", {0: 0.7, 1: 0.7})
    make_e7(root, "e7")
    make_e7(root, "e7_profile")
    make_v1(root)
    return root


def test_aggregates_are_taken_across_seeds_and_keep_the_level(runs):
    payload = ex.build_payload(runs)
    row = payload["experiments"]["E1"]["splits"]["row"]
    mlp = row["systems"]["mlp"]["agreement"]
    assert mlp["mean"] == pytest.approx(0.85) and mlp["sd"] == pytest.approx(0.070711, abs=1e-6)
    assert (mlp["min"], mlp["max"], mlp["n"]) == (0.8, 0.9, 2)
    assert row["cell"] == {"noise": 1.0, "missing": 1.0, "training": "matched"}
    assert payload["experiments"]["E1"]["splits"]["profile_by_label"]["systems"]["mlp"]["agreement"]["sd"] == 0.0

    conformal = payload["experiments"]["E7"]["splits"]["row"]["conformal"]["LAC"]["0.1"]
    assert conformal["metrics"]["coverage"]["mean"] == pytest.approx(0.905)
    assert conformal["coverage_min_over_splits"] == 0.9 and conformal["n_splits_total"] == 4
    bands = payload["experiments"]["E7"]["splits"]["row"]["coverage_by_missing_fields"]
    assert set(bands) == {"0", "1", "2+"} and bands["0"]["coverage"]["mean"] == pytest.approx(0.95)
    assert set(payload["experiments"]["E7"]["splits"]["row"]["selective"]) == {"mlp_maxprob", "gb_maxprob"}

    v1 = payload["experiments"]["V1"]
    assert v1["duplicates_in_test"]["share_true_duplicate"]["mean"] == pytest.approx(0.5)
    assert set(v1["new_profile_splits"]) == {"profile", "profile_by_label"}

    assert payload["evidence_level"] == "N1" and "não validade clínica" in payload["evidence_notice"]
    assert all(payload["experiments"][name]["evidence_level"] == "N1" for name in ("E1", "E7", "V1"))


def test_export_keeps_no_accuracy_word_and_no_local_path(runs):
    text = ex.dumps(ex.build_payload(runs))
    lowered = text.lower()
    assert "accuracy" not in lowered and "acurácia" not in lowered
    assert "someone" not in text and "secret folder" not in text and "\\\\" not in text
    assert json.loads(text)["experiments"]["E1"]["splits"]["row"]["source"]["command"].startswith("e1.py --seeds 0 1")


def test_export_is_deterministic(runs):
    assert ex.dumps(ex.build_payload(runs)) == ex.dumps(ex.build_payload(runs))


def test_missing_runs_folder_fails_with_a_clear_message(tmp_path, capsys):
    assert ex.main(["--runs", str(tmp_path / "nowhere"), "--out", str(tmp_path / "out.json")]) == 1
    assert "runs/ não existe" in capsys.readouterr().err
    assert not (tmp_path / "out.json").exists()


def test_no_runs_argument_and_no_variable_fails_with_a_clear_message(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("PARA_RUNS_DIR", raising=False)
    assert ex.main(["--out", str(tmp_path / "out.json")]) == 1
    assert "PARA_RUNS_DIR" in capsys.readouterr().err


def test_missing_file_inside_runs_names_the_file(runs, tmp_path, capsys):
    (runs / "e7" / "marginal.csv").unlink()
    assert ex.main(["--runs", str(runs), "--out", str(tmp_path / "out.json")]) == 1
    assert "e7/marginal.csv" in capsys.readouterr().err


def test_runs_folder_from_the_environment_variable(runs, tmp_path, monkeypatch):
    monkeypatch.setenv("PARA_RUNS_DIR", str(runs))
    out = tmp_path / "nested" / "transparency.json"
    assert ex.main(["--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] == ex.SCHEMA_VERSION
    assert "\r" not in out.read_text(encoding="utf-8")  # LF on every platform: the file is committed


def test_rule_groups_come_from_the_coverage_document():
    groups = ex.parse_rule_groups(ex.RULES_COVERAGE_DOC.read_text(encoding="utf-8"))
    by_category = {}
    for group in groups:
        by_category.setdefault(group["category"], []).append(group["group"])
    assert "Visual" in by_category["implemented"]
    assert {"Encefálicos", "Petra", "Cadeira e arremesso sentado"} <= set(by_category["provisional"])
    assert any(g["group"].startswith("Membros, em pé") for g in groups if g["category"] == "partial")


def test_model_card_is_none_without_a_checkpoint(tmp_path):
    assert ex.export_model_card(tmp_path) is None
