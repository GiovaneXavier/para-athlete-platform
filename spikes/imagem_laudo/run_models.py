"""image-and-report check PR 3 step B runner. Run from the repository root with the NEW environment (never the project's own):

    set PYTHONPATH=src;spikes/imagem_laudo
    <venv-imagem-laudo>\\Scripts\\python.exe spikes/imagem_laudo/run_models.py image --model smol --level 1 --subset eval --mirror
    ... report --level 1 --subset eval
    ... pipeline --model smol --level 1 --subset eval
    ... (clip_baseline.py is separate)

Everything is written OUTSIDE the repository (paths.RESULTS). Evidence level N1 (synthetic data made by us).
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time

import paths
import subsets
from extractors import ModelExtractor, cached_only, mirrored
from llama_client import LlamaServer
from para_triage.consistency import errors, metrics, pipeline
from para_triage.consistency.metrics import wilson
from para_triage.consistency.schema import ATTRIBUTES, LEVEL1_ATTRIBUTES, UNKNOWN

MODELS = {"smol": ("SmolVLM2-2.2B", paths.SMOLVLM2), "qwen": ("Qwen2.5-VL-7B", paths.QWEN_VL_7B)}


def records_for(level: int, subset: str) -> list:
    return subsets.records(level, subset)


def pct(k: int, n: int) -> str:
    if n == 0:
        return "-"
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f}% ({k}/{n}; {100 * lo:.1f} a {100 * hi:.1f})"


def attribute_accuracy(records, read) -> dict[str, tuple[int, int]]:
    """Reads against the label, per attribute, over attributes whose true value is known (not `?`)."""
    out = {a: [0, 0] for a in ATTRIBUTES}
    for r in records:
        got = read(r.png)
        for a in (LEVEL1_ATTRIBUTES if r.level == 1 else ATTRIBUTES):
            truth = getattr(r.attrs, a)
            if truth == UNKNOWN:
                continue
            out[a][1] += 1
            out[a][0] += int(getattr(got, a) == truth)
    return {a: (v[0], v[1]) for a, v in out.items() if v[1]}


def timing_line(extractor: ModelExtractor, server: LlamaServer) -> str:
    s = extractor.seconds
    if not s:
        return "tempo: nada pedido ao modelo nesta execução (tudo veio do cache)"
    return (f"tempo por pedido: mediana {statistics.median(s):.1f} s, média {statistics.mean(s):.1f} s, mín {min(s):.1f} s, máx {max(s):.1f} s "
            f"({len(s)} pedidos); memória do servidor: pico {server.peak_mb / 1024:.2f} GB; falhas: {extractor.failures}")


def cmd_image(args) -> None:
    name, (model, mmproj) = MODELS[args.model]
    records = records_for(args.level, args.subset)
    if args.limit:
        records = records[: args.limit]
    cache = paths.RESULTS / f"image_{args.model}_{args.prompt}.jsonl"
    print(f"{name}: nível {args.level}, {len(records)} imagens (subconjunto {args.subset}, prompt {args.prompt}), cache {cache.name}", flush=True)
    t0 = time.time()
    with LlamaServer(model, mmproj, port=args.port, name=f"{args.model}_image") as server:
        extractor = ModelExtractor(server, "image", cache, args.prompt)
        for done, r in enumerate(records, 1):
            extractor(r.png)
            if done <= args.mirror:  # the mirrored picture only for the first `--mirror` images
                extractor(mirrored(r.png))
            if done % 5 == 0:
                print(f"  {done}/{len(records)} em {time.time() - t0:.0f} s", flush=True)
        print(timing_line(extractor, server))
    print(f"total {time.time() - t0:.0f} s")
    print_image_tables(args.model, args.prompt, args.level, records, args.mirror)


def print_image_tables(model: str, prompt: str, level: int, records, mirror: int) -> None:
    read = cached_only("image", paths.RESULTS / f"image_{model}_{prompt}.jsonl")
    print(f"\nAcerto por atributo do extrator de imagem {model}, nível {level}, contra o rótulo (N1; Wilson 95%):")
    for a, (k, n) in attribute_accuracy(records, read).items():
        print(f"  {a}: {pct(k, n)}")
    print(f"  leituras ausentes ou com falha no cache: {read.misses['n']}")
    if not mirror:
        return
    records = records[:mirror]
    # Side test: images whose two limbs of a region differ; in the mirrored picture the label sides are swapped.
    for left, right in (("lower_left", "lower_right"), ("upper_left", "upper_right")):
        orig_ok = mirr_ok = same = n = 0
        for r in records:
            l, rr = getattr(r.attrs, left), getattr(r.attrs, right)
            if UNKNOWN in (l, rr) or l == rr:
                continue
            o, m = read(r.png), read(mirrored(r.png))
            po, pm = (getattr(o, left), getattr(o, right)), (getattr(m, left), getattr(m, right))
            n += 1
            orig_ok += int(po == (l, rr))
            mirr_ok += int(pm == (rr, l))
            same += int(po == pm and po != (UNKNOWN, UNKNOWN))
        print(f"  lados ({left.split('_')[0]}), imagens com os dois lados diferentes: {n}: par certo no original {pct(orig_ok, n)}, "
              f"no espelhado {pct(mirr_ok, n)}; mesma leitura nos dois (o espelho não mudou nada): {same}/{n}")


def cmd_report(args) -> None:
    records = records_for(args.level, args.subset)
    pairs = errors.build_pairs([(r.image_id, r.attrs) for r in records], 34)
    items = [p for p in pairs if p.content is not None]
    if args.limit:
        items = items[: args.limit]
    cache = paths.RESULTS / f"report_qwen15_{args.prompt}.jsonl"
    print(f"Qwen2.5-1.5B (laudo): nível {args.level}, {len(items)} laudos, cache {cache.name}", flush=True)
    t0 = time.time()
    model, mmproj = paths.QWEN_TEXT_1_5B
    with LlamaServer(model, mmproj, port=args.port, name="qwen15_report") as server:
        extractor = ModelExtractor(server, "report", cache, args.prompt)
        right = {a: [0, 0] for a in ATTRIBUTES}
        for i, p in enumerate(items, 1):
            got = extractor(p.text)
            for a in ATTRIBUTES:
                right[a][1] += 1
                right[a][0] += int(getattr(got, a) == getattr(p.content.attrs, a))
            if i % 20 == 0:
                print(f"  {i}/{len(items)} em {time.time() - t0:.0f} s", flush=True)
        print(timing_line(extractor, server))
    print(f"total {time.time() - t0:.0f} s")
    print("Acerto do extrator de laudo por atributo (contra o rótulo do laudo, `?` incluído; N1):")
    for a, (k, n) in right.items():
        print(f"  {a}: {pct(k, n)}")


def cmd_pipeline(args) -> None:
    records = records_for(args.level, args.subset)
    pairs = errors.build_pairs([(r.image_id, r.attrs) for r in records], 34)
    images = pipeline.index_images(records)
    image_read = cached_only("image", paths.RESULTS / f"image_{args.model}_{args.image_prompt}.jsonl")
    report_read = cached_only("report", paths.RESULTS / f"report_qwen15_{args.report_prompt}.jsonl")

    def read_image(png):
        a = image_read(png)
        return a.restricted(LEVEL1_ATTRIBUTES) if args.level == 1 else a

    outcomes = pipeline.evaluate(pairs, images, read_image, report_read)
    print(f"Pipeline com extratores {args.model} (imagem, prompt {args.image_prompt}) e Qwen2.5-1.5B (laudo, prompt {args.report_prompt}), nível {args.level}, {len(records)} imagens.")
    print(f"Leituras ausentes ou com falha: imagem {image_read.misses['n']}, laudo {report_read.misses['n']}.\n")
    print(metrics.format_summary(metrics.summarize(outcomes, pairs, draws=1000)))


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("image", "report", "pipeline"):
        p = sub.add_parser(name)
        p.add_argument("--level", type=int, choices=(1, 2), default=1)
        p.add_argument("--subset", choices=("eval", "dev"), default="eval")
        p.add_argument("--prompt", choices=("v1", "v2", "v3", "v4"), default="v2")
        p.add_argument("--port", type=int, default=8081)
        p.add_argument("--limit", type=int, default=0)
        if name == "pipeline":
            p.add_argument("--image-prompt", choices=("v1", "v2", "v3", "v4"), default="v2")
            p.add_argument("--report-prompt", choices=("v1", "v2", "v3", "v4"), default="v3")
        if name in ("image", "pipeline"):
            p.add_argument("--model", choices=tuple(MODELS), default="smol")
        if name == "image":
            p.add_argument("--mirror", type=int, default=0, help="also read the mirrored picture of the first N images")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    {"image": cmd_image, "report": cmd_report, "pipeline": cmd_pipeline}[args.cmd](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
