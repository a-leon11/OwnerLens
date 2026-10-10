"""Command line: python -m ownerlens <command>

  generate   write a fictional registry (CSV files) and its ground truth
  analyze    read a registry, apply the rules, write the findings report and picture
  owners     show who owns one company, route by route
  evaluate   measure detection against the planted structures over several seeds
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from .evaluate import evaluate, markdown_table
from .generate import SEED, generate, write_truth
from .registry import RegistryError, load_registry, write_registry
from .report import draw_network, write_csv, write_markdown
from .rules import analyze

DEFAULT_DATA = "data/registry"
DEFAULT_TRUTH = "data/ground_truth.json"
DEFAULT_REPORTS = "reports"


def _generate(args: argparse.Namespace) -> int:
    registry, truth = generate(args.seed)
    write_registry(registry, args.out)
    write_truth(truth, args.truth)
    print(f"wrote {len(registry.companies)} companies, {len(registry.persons)} people, "
          f"{len(registry.stakes)} stakes to {args.out}")
    print(f"ground truth: {args.truth}")
    return 0


def _analyze(args: argparse.Namespace) -> int:
    registry = load_registry(args.data)
    analysis = analyze(registry)
    out = Path(args.out)
    write_csv(analysis, out / "findings.csv")
    write_markdown(analysis, out / "findings.md")
    titles = draw_network(analysis, out / "ownership_network.png")
    levels = Counter(f.level for f in analysis.findings)
    print(f"{len(registry.companies)} companies analysed, {len(analysis.findings)} flagged "
          f"(high {levels['high']}, medium {levels['medium']}, low {levels['low']})")
    print(f"wrote {out / 'findings.md'}, {out / 'findings.csv'} and {out / 'ownership_network.png'} "
          f"({len(titles)} structures drawn)")
    return 0


def _owners(args: argparse.Namespace) -> int:
    registry = load_registry(args.data)
    if args.company not in registry.companies:
        print(f"unknown company: {args.company}", file=sys.stderr)
        return 2
    analysis = analyze(registry)
    print(analysis.ownership.explain(args.company, analysis.config.ubo_threshold))
    finding = analysis.finding(args.company)
    if finding:
        print(f"\nscore {finding.score} ({finding.level})")
        for flag in finding.flags:
            print(f"  - {flag.rule}: {flag.evidence}")
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    seeds = args.seeds or list(range(SEED, SEED + 20))
    table = markdown_table(evaluate(seeds))
    print(table)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(table + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ownerlens", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    gen = commands.add_parser("generate", help="write a fictional registry")
    gen.add_argument("--seed", type=int, default=SEED)
    gen.add_argument("--out", default=DEFAULT_DATA)
    gen.add_argument("--truth", default=DEFAULT_TRUTH)
    gen.set_defaults(run=_generate)

    ana = commands.add_parser("analyze", help="apply the rules and write the reports")
    ana.add_argument("--data", default=DEFAULT_DATA)
    ana.add_argument("--out", default=DEFAULT_REPORTS)
    ana.set_defaults(run=_analyze)

    own = commands.add_parser("owners", help="show who owns one company")
    own.add_argument("company", help="a company id, for example C-0007")
    own.add_argument("--data", default=DEFAULT_DATA)
    own.set_defaults(run=_owners)

    ev = commands.add_parser("evaluate", help="measure detection against the planted structures")
    ev.add_argument("--seeds", type=int, nargs="*", help="default: 20 seeds starting at the default seed")
    ev.add_argument("--out", help="also write the table to this file")
    ev.set_defaults(run=_evaluate)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except RegistryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
