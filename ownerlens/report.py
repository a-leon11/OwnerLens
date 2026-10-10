"""Turn an Analysis into files a person can read: CSV, Markdown and a picture."""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402

from .registry import is_person  # noqa: E402
from .rules import RULES, Analysis  # noqa: E402

LEVEL_COLORS = {"high": "#d73027", "medium": "#fc8d59", "low": "#fee08b", None: "#e6e6e6"}
NOTE = ("Flags are indicators, not findings of wrongdoing. Each structure has innocent explanations too, "
        "and the score only helps decide what to read first.")


def _owners_text(analysis: Analysis, company_id: str) -> str:
    owners = analysis.ownership.beneficial_owners(company_id, analysis.config.ubo_threshold)
    return "; ".join(f"{h.person_id} {analysis.registry.persons[h.person_id].full_name} {h.effective:.0%}"
                     for h in owners) or "none traced"


def write_csv(analysis: Analysis, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["company_id", "legal_name", "score", "level", "rules", "beneficial_owners", "evidence"])
        for finding in analysis.findings:
            company = analysis.registry.companies[finding.company_id]
            writer.writerow([finding.company_id, company.legal_name, finding.score, finding.level,
                             " ".join(RULES[r].code for r in finding.rules),
                             _owners_text(analysis, finding.company_id),
                             " | ".join(flag.evidence for flag in finding.flags)])


def write_markdown(analysis: Analysis, path: str | Path, top: int = 20) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    levels = Counter(f.level for f in analysis.findings)
    rule_counts = Counter(flag.rule for f in analysis.findings for flag in f.flags)
    total = len(analysis.registry.companies)

    lines = [
        "# Findings report",
        "",
        "> The registry analysed here is fictional and was produced by `python -m ownerlens generate`.",
        f"> {NOTE}",
        "",
        "## Summary",
        "",
        f"- Companies analysed: **{total}**",
        f"- Companies with at least one flag: **{len(analysis.findings)}**",
        f"- High risk (score {analysis.config.high_score}+): **{levels['high']}**, "
        f"medium ({analysis.config.medium_score}-{analysis.config.high_score - 1}): **{levels['medium']}**, "
        f"low: **{levels['low']}**",
        f"- Beneficial owner = effective stake of {analysis.config.ubo_threshold:.0%} or more, counting "
        f"every route through other companies",
        "",
        "## Flags by rule",
        "",
        "| Rule | What it looks for | Points | Companies flagged |",
        "|---|---|---|---|",
    ]
    for name, info in RULES.items():
        lines.append(f"| {info.code} | {info.title} | {info.points} | {rule_counts[name]} |")

    lines += ["", f"## Highest-scoring companies (top {top})", "",
              "| Company | Score | Level | Rules | Beneficial owners | Evidence |", "|---|---|---|---|---|---|"]
    for finding in analysis.findings[:top]:
        company = analysis.registry.companies[finding.company_id]
        lines.append("| {id} {name} | {score} | {level} | {rules} | {owners} | {evidence} |".format(
            id=finding.company_id, name=company.legal_name, score=finding.score, level=finding.level,
            rules=" ".join(RULES[r].code for r in finding.rules), owners=_owners_text(analysis, finding.company_id),
            evidence="<br>".join(flag.evidence for flag in finding.flags)))
    lines += ["", f"The full list, with every flag, is in `findings.csv`. {NOTE}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


# -- the picture -------------------------------------------------------------------------
def _display_graph(analysis: Analysis) -> nx.Graph:
    """People, companies and the addresses that host many companies, joined by ownership,
    directorship and address links."""
    registry = analysis.registry
    graph = nx.Graph()
    for stake in registry.stakes:
        graph.add_edge(stake.owner_id, stake.company_id, kind="owns", label=f"{stake.percent:g}%")
    for directorship in registry.directorships:
        if not graph.has_edge(directorship.person_id, directorship.company_id):
            graph.add_edge(directorship.person_id, directorship.company_id, kind="directs", label="")
    crowded = Counter(c.address_id for c in registry.companies.values())
    for company in registry.companies.values():
        if crowded[company.address_id] >= analysis.config.mass_address_min:
            graph.add_edge(company.company_id, company.address_id, kind="address", label="")
    return graph


def _separate(position: dict, min_distance: float = 0.16, passes: int = 40) -> dict:
    """Push apart nodes that landed on top of each other, so no label is hidden."""
    names = sorted(position)
    for _ in range(passes):
        moved = False
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                dx, dy = position[b][0] - position[a][0], position[b][1] - position[a][1]
                distance = (dx * dx + dy * dy) ** 0.5
                if distance < min_distance:
                    dx, dy = (dx, dy) if distance > 1e-9 else (1.0, 0.0)
                    distance = max(distance, 1e-9) if distance > 1e-9 else 1.0
                    push = (min_distance - distance) / 2 + 0.005
                    ux, uy = dx / distance, dy / distance
                    position[a] = (position[a][0] - ux * push, position[a][1] - uy * push)
                    position[b] = (position[b][0] + ux * push, position[b][1] + uy * push)
                    moved = True
        if not moved:
            break
    return position


def draw_network(analysis: Analysis, path: str | Path, max_panels: int = 6, max_nodes: int = 30) -> list[str]:
    """Draw the most instructive flagged structures, one panel each. Returns the panel titles."""
    graph = _display_graph(analysis)
    level_of = {f.company_id: f.level for f in analysis.findings}
    rules_of = {f.company_id: f.rules for f in analysis.findings}

    candidates = []
    for component in nx.connected_components(graph):
        flagged = [c for c in component if c in level_of and level_of[c] in ("medium", "high")]
        if flagged and len(component) <= max_nodes:
            rules = {r for c in flagged for r in rules_of[c]}
            best = max(next(f.score for f in analysis.findings if f.company_id == c) for c in flagged)
            candidates.append((best, len(component), sorted(component), rules))
    chosen, covered = [], set()
    while len(chosen) < max_panels:
        # next panel: the structure that explains the most rules not shown yet (bigger ones first)
        options = [c for c in candidates if c[3] - covered and c[2] not in [n for n, _ in chosen]]
        if not options:
            break
        best = max(options, key=lambda c: (len(c[3] - covered), c[0], c[1], c[2]))
        chosen.append((best[2], best[3]))
        covered |= best[3]

    columns = 3
    rows = max(1, -(-len(chosen) // columns))
    figure, axes = plt.subplots(rows, columns, figsize=(5.2 * columns, 4.6 * rows))
    axes = list(axes.flat) if hasattr(axes, "flat") else [axes]
    titles = []
    for axis, (nodes, rules) in zip(axes, chosen):
        sub = nx.Graph()                      # built in sorted order, so the picture is identical on every run
        sub.add_nodes_from(nodes)
        sub.add_edges_from(sorted(((u, v, d) for u, v, d in graph.subgraph(nodes).edges(data=True)),
                                  key=lambda edge: (min(edge[0], edge[1]), max(edge[0], edge[1]))))
        position = nx.spring_layout(sub, seed=3, k=1.4 / max(len(nodes), 1) ** 0.5, iterations=300)
        position = _separate({n: tuple(xy) for n, xy in position.items()})
        owns = [(u, v) for u, v, d in sub.edges(data=True) if d["kind"] == "owns"]
        directs = [(u, v) for u, v, d in sub.edges(data=True) if d["kind"] == "directs"]
        address = [(u, v) for u, v, d in sub.edges(data=True) if d["kind"] == "address"]
        nx.draw_networkx_edges(sub, position, edgelist=directs, ax=axis, style="dashed", edge_color="#999999", width=0.8)
        nx.draw_networkx_edges(sub, position, edgelist=address, ax=axis, style="dotted", edge_color="#666666", width=1.0)
        nx.draw_networkx_edges(sub, position, edgelist=owns, ax=axis, edge_color="#333333", width=1.2)
        people = [n for n in nodes if is_person(n)]
        companies = [n for n in nodes if n.startswith("C-")]
        places = [n for n in nodes if n.startswith("A-")]
        nx.draw_networkx_nodes(sub, position, nodelist=people, ax=axis, node_shape="o", node_size=260,
                               node_color="#9ecae1", edgecolors="#3a6e8f")
        nx.draw_networkx_nodes(sub, position, nodelist=companies, ax=axis, node_shape="s", node_size=330,
                               node_color=[LEVEL_COLORS[level_of.get(n)] for n in companies], edgecolors="#444444")
        nx.draw_networkx_nodes(sub, position, nodelist=places, ax=axis, node_shape="D", node_size=300,
                               node_color="#bdbdbd", edgecolors="#555555")
        nx.draw_networkx_labels(sub, position, ax=axis, font_size=5)
        if len(nodes) <= 14:
            labels = {(u, v): d["label"] for u, v, d in sub.edges(data=True) if d["kind"] == "owns"}
            nx.draw_networkx_edge_labels(sub, position, edge_labels=labels, ax=axis, font_size=6,
                                         font_color="#b30000", bbox=dict(alpha=0))
        title = " + ".join(RULES[r].title for r in sorted(rules, key=lambda r: RULES[r].code))
        titles.append(title)
        axis.set_title(title, fontsize=9, wrap=True)
        axis.set_axis_off()
    for axis in axes[len(chosen):]:
        axis.set_axis_off()

    legend = [
        plt.Line2D([], [], marker="o", color="w", markerfacecolor="#9ecae1", markeredgecolor="#3a6e8f", markersize=9, label="person"),
        plt.Line2D([], [], marker="s", color="w", markerfacecolor=LEVEL_COLORS["high"], markeredgecolor="#444", markersize=9, label="company: high"),
        plt.Line2D([], [], marker="s", color="w", markerfacecolor=LEVEL_COLORS["medium"], markeredgecolor="#444", markersize=9, label="company: medium"),
        plt.Line2D([], [], marker="s", color="w", markerfacecolor=LEVEL_COLORS["low"], markeredgecolor="#444", markersize=9, label="company: low"),
        plt.Line2D([], [], marker="s", color="w", markerfacecolor=LEVEL_COLORS[None], markeredgecolor="#444", markersize=9, label="company: no flag"),
        plt.Line2D([], [], marker="D", color="w", markerfacecolor="#bdbdbd", markeredgecolor="#555", markersize=9, label="address"),
        plt.Line2D([], [], color="#333333", label="owns (percent)"),
        plt.Line2D([], [], color="#999999", linestyle="dashed", label="directs"),
        plt.Line2D([], [], color="#666666", linestyle="dotted", label="registered at"),
    ]
    figure.legend(handles=legend, loc="lower center", ncol=5, fontsize=8, frameon=False)
    figure.suptitle("Flagged structures in the fictional registry", fontsize=12)
    figure.tight_layout(rect=(0, 0.07, 1, 0.96))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return titles
