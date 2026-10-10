"""Red-flag rules and the company risk score.

Each rule looks for one structure that is often worth a closer look in company due
diligence. A flag is an INDICATOR, not a finding of wrongdoing: every one of these
structures also has innocent explanations. The score only helps decide what to read
first.

Every rule adds a fixed number of points to a company (see RULES), the points are added
up and capped at 100, and the thresholds in Config turn the total into a level.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field

from .ownership import UBO_THRESHOLD, Ownership
from .registry import Registry


@dataclass(frozen=True)
class RuleInfo:
    code: str
    points: int
    title: str
    why: str


RULES: dict[str, RuleInfo] = {
    "circular_ownership": RuleInfo("R1", 30, "Circular ownership",
                                   "Companies that own each other make it hard to say who controls what."),
    "layering": RuleInfo("R2", 25, "Layered ownership",
                         "A beneficial owner behind many intermediary companies can hide who is in control."),
    "mass_address": RuleInfo("R3", 20, "Mass registration address",
                             "Many companies at one address is typical of shell factories, but also of "
                             "corporate groups and virtual offices."),
    "nominee_director": RuleInfo("R4", 30, "Nominee-style director",
                                 "One person directing many companies without owning them can be a front for "
                                 "the real owners."),
    "threshold_dodging": RuleInfo("R5", 25, "Stake split to stay under the threshold",
                                  "Holding a stake through several small routes keeps each one below the "
                                  "beneficial-owner threshold."),
    "unresolved_ownership": RuleInfo("R6", 30, "Ownership that cannot be traced",
                                     "If part of a company cannot be traced to a person, the owner is unknown."),
    "rapid_dissolution": RuleInfo("R7", 20, "Closed within a year",
                                  "Companies that open and close quickly are sometimes used once and thrown away."),
}


@dataclass(frozen=True)
class Config:
    ubo_threshold: float = UBO_THRESHOLD       # effective stake that makes a person a beneficial owner
    min_intermediaries: int = 3                # R2: companies between the person and the target
    mass_address_min: int = 6                  # R3: companies at one address
    nominee_min_directorships: int = 8         # R4: companies directed by one person
    nominee_max_stake: float = 0.05            # R4: "owns nothing" means under this effective stake
    nominee_min_share: float = 0.75            # R4: share of those companies where the person owns nothing
    unresolved_medium: float = 0.25            # R6: share of ownership that cannot be traced (15 points)
    unresolved_high: float = 0.50              # R6: same, full points
    rapid_dissolution_days: int = 365          # R7: lifetime at or below this many days
    medium_score: int = 25                     # level thresholds
    high_score: int = 50


@dataclass(frozen=True)
class Flag:
    company_id: str
    rule: str
    points: int
    evidence: str


@dataclass(frozen=True)
class CompanyFinding:
    company_id: str
    score: int
    level: str
    flags: tuple[Flag, ...]

    @property
    def rules(self) -> tuple[str, ...]:
        return tuple(flag.rule for flag in self.flags)


@dataclass
class Analysis:
    registry: Registry
    ownership: Ownership
    config: Config
    findings: list[CompanyFinding] = field(default_factory=list)      # flagged companies, highest score first

    def finding(self, company_id: str) -> CompanyFinding | None:
        return next((f for f in self.findings if f.company_id == company_id), None)

    def at_least(self, level: str) -> list[CompanyFinding]:
        order = {"low": 1, "medium": 2, "high": 3}
        return [f for f in self.findings if order[f.level] >= order[level]]


# -- the rules ---------------------------------------------------------------------------
def _circular(registry: Registry, ownership: Ownership, config: Config) -> list[Flag]:
    flags = []
    for loop in ownership.loops:
        path = " > ".join(ownership.loop_path(loop))
        for company_id in loop:
            flags.append(Flag(company_id, "circular_ownership", RULES["circular_ownership"].points,
                              f"part of an ownership loop: {path}"))
    return flags


def _layering(registry: Registry, ownership: Ownership, config: Config) -> list[Flag]:
    flags = []
    for company_id, holdings in ownership.holdings.items():
        for holding in ownership.beneficial_owners(company_id, config.ubo_threshold):
            shortest = min(holding.routes, key=lambda r: r.intermediaries)
            if shortest.intermediaries >= config.min_intermediaries:
                name = registry.persons[holding.person_id].full_name
                flags.append(Flag(company_id, "layering", RULES["layering"].points,
                                  f"{name} ({holding.person_id}) owns {holding.effective:.0%} but the closest route "
                                  f"passes through {shortest.intermediaries} intermediary companies"))
    return flags


def _mass_address(registry: Registry, ownership: Ownership, config: Config) -> list[Flag]:
    by_address: dict[str, list[str]] = defaultdict(list)
    for company in registry.companies.values():
        by_address[company.address_id].append(company.company_id)
    flags = []
    for address_id, members in by_address.items():
        if len(members) >= config.mass_address_min:
            address = registry.addresses[address_id]
            for company_id in members:
                flags.append(Flag(company_id, "mass_address", RULES["mass_address"].points,
                                  f"{len(members)} companies are registered at {address.street}, {address.city}"))
    return flags


def _nominee(registry: Registry, ownership: Ownership, config: Config) -> list[Flag]:
    directed: dict[str, set[str]] = defaultdict(set)
    for directorship in registry.directorships:
        directed[directorship.person_id].add(directorship.company_id)
    flags = []
    for person_id, companies in directed.items():
        if len(companies) < config.nominee_min_directorships:
            continue
        owns_nothing = [c for c in companies if ownership.effective_stake(person_id, c) < config.nominee_max_stake]
        if len(owns_nothing) / len(companies) >= config.nominee_min_share:
            name = registry.persons[person_id].full_name
            for company_id in sorted(owns_nothing):
                flags.append(Flag(company_id, "nominee_director", RULES["nominee_director"].points,
                                  f"{name} ({person_id}) directs {len(companies)} companies and owns under "
                                  f"{config.nominee_max_stake:.0%} of {len(owns_nothing)} of them"))
    return flags


def _threshold_dodging(registry: Registry, ownership: Ownership, config: Config) -> list[Flag]:
    flags = []
    for company_id, holdings in ownership.holdings.items():
        for holding in ownership.beneficial_owners(company_id, config.ubo_threshold):
            biggest = max(route.share for route in holding.routes)
            # a total at the threshold with every route below it can only happen with two or more routes
            if biggest < config.ubo_threshold - 1e-9:
                name = registry.persons[holding.person_id].full_name
                flags.append(Flag(company_id, "threshold_dodging", RULES["threshold_dodging"].points,
                                  f"{name} ({holding.person_id}) holds {holding.effective:.0%} through "
                                  f"{len(holding.routes)} routes, none above {biggest:.0%}"))
    return flags


def _unresolved(registry: Registry, ownership: Ownership, config: Config) -> list[Flag]:
    flags = []
    for company_id in registry.companies:
        share = ownership.unresolved(company_id)
        if share >= config.unresolved_high - 1e-9:
            points = RULES["unresolved_ownership"].points
        elif share >= config.unresolved_medium - 1e-9:
            points = RULES["unresolved_ownership"].points // 2
        else:
            continue
        flags.append(Flag(company_id, "unresolved_ownership", points,
                          f"{share:.0%} of the ownership cannot be traced to a person"))
    return flags


def _rapid_dissolution(registry: Registry, ownership: Ownership, config: Config) -> list[Flag]:
    flags = []
    for company in registry.companies.values():
        if company.dissolved is None:
            continue
        lifetime = (company.dissolved - company.incorporated).days
        if lifetime <= config.rapid_dissolution_days:
            flags.append(Flag(company.company_id, "rapid_dissolution", RULES["rapid_dissolution"].points,
                              f"dissolved {lifetime} days after it was incorporated"))
    return flags


_RULE_FUNCTIONS = (_circular, _layering, _mass_address, _nominee, _threshold_dodging, _unresolved, _rapid_dissolution)


def level_for(score: int, config: Config) -> str:
    if score >= config.high_score:
        return "high"
    if score >= config.medium_score:
        return "medium"
    return "low"


def analyze(registry: Registry, config: Config | None = None) -> Analysis:
    """Run every rule and score every company that has at least one flag."""
    config = config or Config()
    ownership = Ownership(registry)
    by_company: dict[str, list[Flag]] = defaultdict(list)
    for rule in _RULE_FUNCTIONS:
        for flag in rule(registry, ownership, config):
            by_company[flag.company_id].append(flag)

    findings = []
    for company_id, flags in by_company.items():
        score = min(100, sum(flag.points for flag in flags))
        findings.append(CompanyFinding(company_id, score, level_for(score, config), tuple(flags)))
    findings.sort(key=lambda f: (-f.score, f.company_id))
    return Analysis(registry, ownership, config, findings)
