"""image-and-report check, PR 2: the package is isolated (design note section 12, "guarda de isolamento").

* it imports no `torch`, no `transformers` and nothing that reaches the network, and no other module of `para_triage`;
* nothing else in `para_triage` imports it (the API, the rule engine and the rule book do not know it exists);
* no image of a person, no model weight and no real report is in the repository;
* the dependencies in `pyproject.toml` are the same as before.
"""
import ast
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "para_triage"
CONSISTENCY = PACKAGE / "consistency"

HEAVY_OR_NETWORK = {
    "torch", "torchvision", "torchaudio", "transformers", "tokenizers", "huggingface_hub", "safetensors", "open_clip", "llama_cpp",
    "requests", "httpx", "urllib3", "aiohttp", "http", "urllib", "socket", "ssl", "ftplib", "smtplib", "websockets", "subprocess",
    "PIL", "cv2", "matplotlib", "skimage", "scipy", "pandas", "sklearn",
}
ALLOWED_THIRD_PARTY = {"numpy"}


def imported_modules(path: Path):
    """(top-level module, level, full dotted name) of every import in a file."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found += [(a.name.split(".")[0], 0, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            found.append(((node.module or "").split(".")[0], node.level, ("." * node.level) + (node.module or "")))
    return found


def test_the_package_imports_only_the_standard_library_numpy_and_itself():
    stdlib = set(sys.stdlib_module_names)
    for path in sorted(CONSISTENCY.glob("*.py")):
        for top, level, full in imported_modules(path):
            if level == 1:
                continue  # a sibling module of the package
            assert level == 0, f"{path.name}: {full} reaches out of the package"
            assert top not in HEAVY_OR_NETWORK, f"{path.name} imports {full}"
            assert top in stdlib or top in ALLOWED_THIRD_PARTY, f"{path.name} imports {full}, which is neither the standard library nor numpy"
            assert top != "para_triage", f"{path.name}: use relative imports inside the package"


def test_the_scan_would_catch_an_import(tmp_path):
    sample = tmp_path / "x.py"
    for code, top in (("import torch", "torch"), ("from transformers import AutoModel", "transformers"), ("import urllib.request", "urllib"),
                      ("from ..rules import RuleEngine", "rules"), ("from para_triage.api import app", "para_triage")):
        sample.write_text(code + "\n", encoding="utf-8")
        [(found, level, _)] = imported_modules(sample)
        assert found == top and (found in HEAVY_OR_NETWORK or level == 2 or found == "para_triage")  # a heavy import, a jump out of the package, or an absolute one


def test_importing_every_module_of_the_package_loads_no_model_library():
    modules = sorted(p.stem for p in CONSISTENCY.glob("*.py") if p.stem not in ("__main__",))
    code = (
        "import importlib, sys\n"
        f"for name in {modules!r}:\n"
        "    importlib.import_module('para_triage.consistency' + ('' if name == '__init__' else '.' + name))\n"
        "bad = sorted(m for m in ('torch', 'transformers', 'safetensors', 'huggingface_hub', 'open_clip', 'requests', 'httpx', 'PIL', 'cv2') if m in sys.modules)\n"
        "assert not bad, bad\n"
        "assert not any(m.startswith('para_triage.') and not m.startswith('para_triage.consistency') for m in sys.modules), "
        "[m for m in sys.modules if m.startswith('para_triage.') and not m.startswith('para_triage.consistency')]\n"
    )
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), os.environ.get("PYTHONPATH", "")])}
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_nothing_else_in_the_package_imports_the_consistency_check():
    offenders = {}
    for path in PACKAGE.rglob("*.py"):
        if CONSISTENCY in path.parents:
            continue
        hits = [full for top, level, full in imported_modules(path) if "consistency" in full.split(".")]
        # `from .. import consistency` and `from . import consistency` name the module in the alias list
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and any(a.name == "consistency" for a in node.names):
                hits.append("import consistency")
        if hits:
            offenders[str(path.relative_to(PACKAGE))] = hits
    assert not offenders, offenders


def test_no_route_of_the_api_comes_from_the_consistency_check():
    pytest.importorskip("fastapi")
    from para_triage.api.app import create_app

    paths = create_app().openapi()["paths"]
    assert not any("consistency" in p or "imagem_laudo" in p.lower() or "conferencia" in p for p in paths)


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=ROOT, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [ROOT / line for line in out.splitlines() if line]


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg", ".ico", ".heic"}
WEIGHT_SUFFIXES = {".gguf", ".safetensors", ".pt", ".pth", ".bin", ".onnx", ".ckpt", ".h5", ".npz", ".npy"}
# Images that were already in the repository before image-and-report check and have nothing to do with it (a favicon, figures of a paper template).
KNOWN_IMAGES = {"web/src/app/favicon.ico"}


# Published on purpose (24/11/2026, so that anyone reading the repository can see the images and the model): a few of OUR synthetic
# images (drawn by our own code, no person in them) and the two weight files of the image-against-form experiment network (3.9 MB each, trained on synthetic
# data only). Anything else, and above all a real photo or an image from LEXI, is still refused.
SYNTHETIC_EXAMPLES_DIR = "docs/exemplos-imagens/"
PESOS_IMAGEM_DIR = "docs/modelo-imagem/"
MAX_EXAMPLES = 20
MAX_WEIGHT_BYTES = 5_000_000


def test_no_new_image_and_no_model_weight_is_in_the_repository():
    files = [p for p in tracked_files() if p.exists()]
    rel = {p: p.relative_to(ROOT).as_posix() for p in files}
    examples = {r for r in rel.values() if r.startswith(SYNTHETIC_EXAMPLES_DIR)}
    images = {r for p, r in rel.items() if p.suffix.lower() in IMAGE_SUFFIXES} - examples
    weights = [r for p, r in rel.items() if p.suffix.lower() in WEIGHT_SUFFIXES and not r.startswith(PESOS_IMAGEM_DIR)]
    assert images <= KNOWN_IMAGES, sorted(images - KNOWN_IMAGES)
    assert not weights, weights
    # the exceptions are narrow: PNG only, a handful of files, small weights, state dicts of the image-against-form experiment network
    assert len(examples) <= MAX_EXAMPLES and all(r.endswith(".png") for r in examples), sorted(examples)
    imagem_formulario = [p for p, r in rel.items() if r.startswith(PESOS_IMAGEM_DIR) and p.suffix.lower() in WEIGHT_SUFFIXES]
    assert all(p.suffix.lower() == ".pt" and p.stat().st_size < MAX_WEIGHT_BYTES for p in imagem_formulario), [p.name for p in imagem_formulario]


def test_the_image_files_hold_code_text_and_the_manifest_only():
    allowed_suffixes = {".py", ".md", ".csv"}
    mine = [p for p in tracked_files() if p.exists() and (CONSISTENCY in p.parents or "consistencia" in p.name or p.name.startswith("test_consistency"))]
    assert mine, "the image-and-report check files should be found"
    assert {p.suffix for p in mine} <= allowed_suffixes, sorted({p.suffix for p in mine} - allowed_suffixes)
    manifest = ROOT / "docs" / "consistencia-imagem-laudo-manifesto-nivel3.csv"
    assert manifest in mine
    header = manifest.read_text(encoding="utf-8").splitlines()[0]
    assert "commons_page_url" in header and "label_status" in header
    # PR 3 step B: the model extractors live in spikes/imagem_laudo as code and text only; weights, binaries, images and results stay outside the repo
    spike = [p for p in tracked_files() if p.exists() and (ROOT / "spikes" / "imagem_laudo") in p.parents]
    assert {p.suffix for p in spike} <= {".py", ".md", ".txt"}, sorted({p.suffix for p in spike})
    assert all(p.stat().st_size < 100_000 for p in spike), "nothing big belongs in the spike folder"


def test_the_dependencies_are_the_same_as_before_imagem_laudo():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["dependencies"] == ["numpy", "pandas", "pyyaml", "scikit-learn", "torch"]
    assert data["project"]["optional-dependencies"]["api"] == ["fastapi", "uvicorn[standard]"]
    assert data["project"]["optional-dependencies"]["dev"] == ["pytest", "httpx"]
    assert "consistency" not in str(data["tool"]["setuptools"])
