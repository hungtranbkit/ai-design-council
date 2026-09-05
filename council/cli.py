"""CLI entry point.

    python -m council run --brief examples/qr_restaurant.md --provider mock
    python -m council run --brief examples/qr_restaurant.md --provider mock --mode single-agent
    python -m council compare --brief examples/qr_restaurant.md --provider mock
    python -m council report <run_id>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from council import artifacts, compare as compare_mod, metrics as metrics_mod, report as report_mod
from council.pipeline.orchestrator import CouncilOrchestrator
from council.pipeline.single_agent import run_solo
from council.providers import PROVIDER_NAMES, get_provider


def _cmd_run(args: argparse.Namespace) -> int:
    brief_path = Path(args.brief)
    if not brief_path.exists():
        print(f"error: brief file not found: {brief_path}", file=sys.stderr)
        return 1
    brief_text = brief_path.read_text(encoding="utf-8")
    runs_dir = Path(args.runs_dir)
    provider = get_provider(args.provider)

    run_dir = artifacts.make_run_dir(runs_dir, brief_path.stem, args.mode, run_id=args.run_id)
    artifacts.save_meta(run_dir, run_id=run_dir.name, mode=args.mode, provider=provider.name, brief_path=str(brief_path))
    artifacts.save_brief(run_dir, brief_text)

    if args.mode == "council":
        orchestrator = CouncilOrchestrator(provider=provider)
        result = orchestrator.run(brief_text)
        metrics = metrics_mod.compute_council_metrics(result)
        artifacts.save_council_artifacts(run_dir, result)
        artifacts.save_metrics(run_dir, metrics)
        artifacts.save_calls(run_dir, result.calls)
        report_md = report_mod.render_council_report(run_id=run_dir.name, brief_text=brief_text, result=result, metrics=metrics)
    else:
        result = run_solo(provider, brief_text)
        metrics = metrics_mod.compute_solo_metrics(result)
        artifacts.save_solo_artifacts(run_dir, result)
        artifacts.save_metrics(run_dir, metrics)
        artifacts.save_calls(run_dir, result.calls)
        report_md = report_mod.render_solo_report(run_id=run_dir.name, brief_text=brief_text, result=result, metrics=metrics)

    artifacts.save_final_report(run_dir, report_md)

    print(f"run complete: {run_dir}")
    print(f"  mode={args.mode} provider={provider.name}")
    print(f"  requirements={metrics['requirements_count']} edge_cases={metrics['edge_cases_count']} "
          f"risks={metrics['risks_count']} mind_changes={metrics['mind_changes_count']} "
          f"unresolved={metrics['unresolved_count']}")
    print(f"  final report: {run_dir / 'final_report.md'}")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    brief_path = Path(args.brief)
    if not brief_path.exists():
        print(f"error: brief file not found: {brief_path}", file=sys.stderr)
        return 1
    runs_dir = Path(args.runs_dir)
    provider = get_provider(args.provider)

    comp = compare_mod.run_comparison(provider=provider, brief_path=brief_path, runs_dir=runs_dir, run_id_prefix=args.run_id_prefix)

    comparisons_dir = runs_dir / "comparisons"
    comparisons_dir.mkdir(parents=True, exist_ok=True)
    compare_id = args.run_id_prefix or f"{comp.council_run_dir.name}__vs__{comp.solo_run_dir.name}"
    compare_dir = comparisons_dir / compare_id
    suffix = 2
    base = compare_dir
    while compare_dir.exists():
        compare_dir = base.parent / f"{base.name}-{suffix}"
        suffix += 1
    compare_dir.mkdir(parents=True)

    comparison_json = compare_mod.render_comparison_json(comp)
    comparison_md = compare_mod.render_comparison_markdown(comp)
    artifacts.write_json(compare_dir / "comparison.json", comparison_json)
    artifacts.write_text(compare_dir / "comparison.md", comparison_md)

    print(f"council run: {comp.council_run_dir}")
    print(f"solo run:    {comp.solo_run_dir}")
    print(f"comparison:  {compare_dir}/comparison.md")
    print("")
    print(comparison_md)
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    runs_dir = Path(args.runs_dir)
    run_dir = runs_dir / args.run_id
    report_path = run_dir / "final_report.md"
    if not report_path.exists():
        print(f"error: no final_report.md for run_id '{args.run_id}' under {runs_dir}", file=sys.stderr)
        return 1
    text = report_path.read_text(encoding="utf-8")
    print(text)
    print(f"\n(report file: {report_path})", file=sys.stderr)
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("error: the web extra is not installed. Run: pip install -e '.[web]'", file=sys.stderr)
        return 1
    print(f"AI Design Council web UI: http://{args.host}:{args.port}  (runs dir: {Path('runs').resolve()})")
    uvicorn.run("council.web.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m council", description="AI Design Council V0")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run one pipeline (council or single-agent) against a brief")
    p_run.add_argument("--brief", required=True, help="path to a brief markdown file")
    p_run.add_argument("--provider", default="mock", choices=PROVIDER_NAMES)
    p_run.add_argument("--mode", default="council", choices=["council", "single-agent"])
    p_run.add_argument("--runs-dir", default="runs")
    p_run.add_argument("--run-id", default=None, help="explicit run id (default: timestamp-based)")
    p_run.set_defaults(func=_cmd_run)

    p_cmp = sub.add_parser("compare", help="run council AND single-agent on the same brief, write comparison.json/md")
    p_cmp.add_argument("--brief", required=True)
    p_cmp.add_argument("--provider", default="mock", choices=PROVIDER_NAMES)
    p_cmp.add_argument("--runs-dir", default="runs")
    p_cmp.add_argument("--run-id-prefix", default=None, help="prefix for both generated run ids and the comparison dir")
    p_cmp.set_defaults(func=_cmd_compare)

    p_report = sub.add_parser("report", help="print a run's final_report.md")
    p_report.add_argument("run_id")
    p_report.add_argument("--runs-dir", default="runs")
    p_report.set_defaults(func=_cmd_report)

    p_serve = sub.add_parser("serve", help="run the web UI + API (FastAPI/uvicorn)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8420)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()  # no-op if .env doesn't exist; mock provider needs no env vars
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
