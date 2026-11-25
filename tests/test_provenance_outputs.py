"""Run provenance and the paper outputs folder handling."""


from para_triage.experiments import protocol as P
from para_triage.experiments.baselines import GbConfig
from para_triage.models import TrainConfig



def test_provenance_separates_code_changes_from_other_changes():
    from para_triage.experiments.provenance import provenance

    p = provenance()
    assert {"commit", "code_tree_dirty", "tree_dirty", "python", "torch", "command"} <= set(p)
    assert isinstance(p["code_tree_dirty"], bool) and isinstance(p["tree_dirty"], bool)
    assert not p["code_tree_dirty"] or p["tree_dirty"]  # a dirty code tree makes the whole tree dirty


def test_paper_outputs_creates_the_output_folders_on_demand_and_leaves_the_default_alone(tmp_path, monkeypatch):
    from para_triage.experiments import e1, paper_outputs

    monkeypatch.setattr(e1, "MLP_GRID", (TrainConfig(hidden=(16,), epochs=2),))
    monkeypatch.setattr(e1, "GB_GRID", (GbConfig(max_iter=3),))
    runs = tmp_path / "runs"
    e1.run_seed(0, runs / "e1", [P.CLEAN_CELL, P.DEFAULT_CELL, (1.0, 2.0)], n_per_label=40)
    e1.aggregate(runs / "e1", [0])
    monkeypatch.chdir(tmp_path)  # a "paper" folder must not appear here when another root is asked for

    out = tmp_path / "somewhere" / "else"
    paper_outputs.main(["--runs", str(runs), "--paper", str(out), "--no-figures"])
    assert (out / "p1" / "tables" / "t_main.tex").exists() and (out / "p4" / "tables" / "t_main.tex").exists()
    assert (out / "p1" / "numbers_exp.tex").exists() and (out / "p4" / "numbers_exp.tex").exists()
    assert not (tmp_path / "paper").exists()
    numbers = (out / "p1" / "numbers_exp.tex").read_text(encoding="utf-8")
    assert "{\\accMLPRow}" in numbers and "{\\accMLP}" in numbers  # the by-row split, with and without the suffix
