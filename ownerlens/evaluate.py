"""Measure the detection against the structures the generator planted.

What this does and does not show: the planted structures were written to match the rules,
so a high recall is a sanity check that the rules and the generator agree, not a claim
about performance on real data. The informative numbers are the false positives: how many
companies that were NOT planted reach medium or high risk, across several random
backgrounds.
"""
from __future__ import annotations

from dataclasses import dataclass

from .generate import generate
from .rules import Analysis, analyze


@dataclass
class SeedResult:
    seed: int
    recall: dict[str, tuple[int, int]]          # pattern -> (found, planted)
    planted_total: int
    planted_medium_plus: int
    other_medium_plus: int                      # companies that were not planted but reach medium or high
    benign_total: int
    benign_medium_plus: int
    background_low_flags: int                   # harmless oddities flagged at low level


def evaluate_seed(seed: int) -> SeedResult:
    registry, truth = generate(seed)
    analysis = analyze(registry)
    return score(analysis, truth, seed)


def score(analysis: Analysis, truth: dict, seed: int) -> SeedResult:
    planted = {c for p in truth["patterns"] for c in p["companies"]}
    benign = {c for group in truth["benign"].values() for c in group}
    recall = {}
    for pattern in truth["patterns"]:
        found = 0
        for company_id in pattern["companies"]:
            finding = analysis.finding(company_id)
            if finding and pattern["rule"] in finding.rules:
                found += 1
        recall[pattern["pattern"]] = (found, len(pattern["companies"]))
    medium_plus = {f.company_id for f in analysis.at_least("medium")}
    low = {f.company_id for f in analysis.findings if f.level == "low"}
    return SeedResult(
        seed=seed, recall=recall, planted_total=len(planted),
        planted_medium_plus=len(planted & medium_plus),
        other_medium_plus=len(medium_plus - planted),
        benign_total=len(benign), benign_medium_plus=len(benign & medium_plus),
        background_low_flags=len(low - planted - benign),
    )


def evaluate(seeds: list[int]) -> list[SeedResult]:
    return [evaluate_seed(seed) for seed in seeds]


def markdown_table(results: list[SeedResult]) -> str:
    patterns = list(results[0].recall)
    lines = ["| Planted structure | Rule | Found | Planted |", "|---|---|---|---|"]
    from .rules import RULES  # local import keeps the module header tidy
    registry, truth = generate(results[0].seed)
    rule_of = {p["pattern"]: p["rule"] for p in truth["patterns"]}
    for pattern in patterns:
        found = sum(r.recall[pattern][0] for r in results)
        planted = sum(r.recall[pattern][1] for r in results)
        lines.append(f"| {pattern} | {RULES[rule_of[pattern]].code} | {found} | {planted} |")
    lines += ["", f"Across {len(results)} random backgrounds (seeds {results[0].seed} to {results[-1].seed}):", "",
              "| Measure | Total |", "|---|---|",
              f"| Planted companies | {sum(r.planted_total for r in results)} |",
              f"| ...of which reach medium or high | {sum(r.planted_medium_plus for r in results)} |",
              f"| Not planted, but reach medium or high (false positives) | {sum(r.other_medium_plus for r in results)} |",
              f"| Harmless lookalike companies | {sum(r.benign_total for r in results)} |",
              f"| ...of which reach medium or high | {sum(r.benign_medium_plus for r in results)} |",
              f"| Harmless oddities flagged at low level | {sum(r.background_low_flags for r in results)} |"]
    return "\n".join(lines)
