"""Who ultimately owns what: effective ownership through layers of companies.

If person P owns 50% of company A and A owns 40% of company B, P effectively owns
50% x 40% = 20% of B. A person can reach a company by several routes; the effective
stake is the sum over all routes.

Circular holdings (A owns part of B and B owns part of A) make the exact answer
ambiguous, so each route is only allowed to visit a company once. Whatever share
cannot be traced to a person that way is reported as "unresolved".
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import networkx as nx

from .registry import Registry, is_person

UBO_THRESHOLD = 0.25   # a commonly used cut-off for "beneficial owner"; configurable
MAX_DEPTH = 10         # longest chain of companies followed upwards


@dataclass(frozen=True)
class Route:
    """One way a person reaches a company: nodes run from the person down to the company."""

    nodes: tuple[str, ...]
    share: float                       # product of the percentages along the route, 0 to 1

    @property
    def intermediaries(self) -> int:
        """Companies sitting between the person and the target (0 means a direct holding)."""
        return len(self.nodes) - 2


@dataclass(frozen=True)
class Holding:
    person_id: str
    company_id: str
    routes: tuple[Route, ...]

    @property
    def effective(self) -> float:
        return sum(route.share for route in self.routes)


class Ownership:
    """The ownership graph of a registry and everything derived from it."""

    def __init__(self, registry: Registry, max_depth: int = MAX_DEPTH) -> None:
        self.registry = registry
        self.max_depth = max_depth
        self.graph = nx.DiGraph()
        self.graph.add_nodes_from(registry.persons)
        self.graph.add_nodes_from(registry.companies)
        for stake in registry.stakes:
            self.graph.add_edge(stake.owner_id, stake.company_id, percent=stake.percent)
        self.holdings: dict[str, list[Holding]] = {c: self._holdings_in(c) for c in registry.companies}
        self.loops: list[list[str]] = self._find_loops()

    # -- computation -------------------------------------------------------------------
    def _holdings_in(self, company_id: str) -> list[Holding]:
        routes: dict[str, list[Route]] = defaultdict(list)

        def climb(node: str, share: float, trail: tuple[str, ...]) -> None:
            for owner in self.graph.predecessors(node):
                if owner in trail:
                    continue                      # a loop: do not go round again
                fraction = share * self.graph[owner][node]["percent"] / 100
                if is_person(owner):
                    routes[owner].append(Route((owner, *reversed(trail)), fraction))
                elif len(trail) < self.max_depth:
                    climb(owner, fraction, (*trail, owner))

        climb(company_id, 1.0, (company_id,))
        return sorted((Holding(person, company_id, tuple(sorted(r, key=lambda x: -x.share)))
                       for person, r in routes.items()),
                      key=lambda h: (-h.effective, h.person_id))

    def _find_loops(self) -> list[list[str]]:
        companies = self.graph.subgraph(self.registry.companies)
        loops = [sorted(component) for component in nx.strongly_connected_components(companies)
                 if len(component) > 1]
        return sorted(loops)

    # -- questions ---------------------------------------------------------------------
    def effective_stake(self, person_id: str, company_id: str) -> float:
        for holding in self.holdings[company_id]:
            if holding.person_id == person_id:
                return holding.effective
        return 0.0

    def beneficial_owners(self, company_id: str, threshold: float = UBO_THRESHOLD) -> list[Holding]:
        """People whose effective stake reaches the threshold."""
        return [h for h in self.holdings[company_id] if h.effective >= threshold - 1e-9]

    def unresolved(self, company_id: str) -> float:
        """The share of the company that cannot be traced to any person (0 to 1)."""
        traced = sum(h.effective for h in self.holdings[company_id])
        return min(1.0, max(0.0, 1.0 - traced)) if traced < 1 - 1e-9 else 0.0

    def loop_path(self, loop: list[str]) -> list[str]:
        """One cycle through the loop, as a closed list of company ids (first == last).

        The cycle starts at the smallest id and always follows the smallest id first, so the
        result is the same on every run.
        """
        members = set(loop)
        start = min(loop)

        def walk(node: str, trail: list[str]) -> list[str] | None:
            for owned in sorted(self.graph.successors(node)):
                if owned == start and len(trail) > 1:
                    return trail + [start]
                if owned in members and owned not in trail:
                    found = walk(owned, trail + [owned])
                    if found:
                        return found
            return None

        return walk(start, [start]) or [start]

    def explain(self, company_id: str, threshold: float = UBO_THRESHOLD) -> str:
        """A plain-text description of who owns a company and how, for the command line."""
        company = self.registry.companies[company_id]
        lines = [f"{company_id}  {company.legal_name}"]
        if not self.holdings[company_id]:
            lines.append("  no person can be traced as an owner")
        for holding in self.holdings[company_id]:
            person = self.registry.persons[holding.person_id]
            tag = "  <- beneficial owner" if holding.effective >= threshold - 1e-9 else ""
            lines.append(f"  {holding.person_id} {person.full_name}: {holding.effective:.1%}{tag}")
            for route in holding.routes:
                lines.append(f"      {route.share:6.1%}  " + " > ".join(route.nodes))
        unresolved = self.unresolved(company_id)
        if unresolved > 0:
            lines.append(f"  {unresolved:.1%} of the company cannot be traced to a person")
        return "\n".join(lines)
