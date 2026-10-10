import datetime as dt

import pytest

from conftest import build
from ownerlens.rules import RULES, Config, analyze, level_for


def rules_for(registry, company_id, config=None):
    finding = analyze(registry, config).finding(company_id)
    return finding.rules if finding else ()


# R1
def test_circular_ownership_is_flagged_for_every_member():
    stakes = [("C-1", "C-2", 45), ("C-2", "C-3", 45), ("C-3", "C-1", 45),
              ("P-1", "C-1", 55), ("P-2", "C-2", 55), ("P-3", "C-3", 55)]
    registry = build(stakes)
    for company in ("C-1", "C-2", "C-3"):
        assert "circular_ownership" in rules_for(registry, company)


def test_a_chain_is_not_circular():
    assert "circular_ownership" not in rules_for(build([("P-1", "C-1", 100), ("C-1", "C-2", 100)]), "C-2")


# R2
@pytest.mark.parametrize("length, expected", [(3, False), (4, True), (5, True)])
def test_layering_needs_three_intermediaries(length, expected):
    stakes = [("P-1", "C-1", 100)] + [(f"C-{i}", f"C-{i + 1}", 100) for i in range(1, length)]
    assert ("layering" in rules_for(build(stakes), f"C-{length}")) is expected


def test_layering_ignores_small_holders():
    # P-1 reaches C-4 through three companies, but only holds 20% of it
    stakes = [("P-1", "C-1", 100), ("C-1", "C-2", 100), ("C-2", "C-3", 100), ("C-3", "C-4", 20), ("P-2", "C-4", 80)]
    assert "layering" not in rules_for(build(stakes), "C-4")


def test_layering_uses_the_closest_route():
    stakes = [("P-1", "C-1", 100), ("C-1", "C-2", 100), ("C-2", "C-3", 100), ("C-3", "C-4", 50), ("P-1", "C-4", 50)]
    assert "layering" not in rules_for(build(stakes), "C-4")      # a direct holding exists


# R3
@pytest.mark.parametrize("count, expected", [(5, False), (6, True)])
def test_mass_address_threshold(count, expected):
    stakes = [(f"P-{i}", f"C-{i}", 100) for i in range(count)]
    registry = build(stakes, address_of={f"C-{i}": "A-shared" for i in range(count)})
    assert ("mass_address" in rules_for(registry, "C-0")) is expected


# R4
def _directed_companies(count, directors_share):
    """P-1 directs `count` companies and holds `directors_share` per cent of each; P-2x holds the rest."""
    stakes = [("P-1", f"C-{i}", directors_share) for i in range(count)]
    stakes += [(f"P-2{i}", f"C-{i}", 100 - directors_share) for i in range(count)]
    return stakes, [("P-1", f"C-{i}") for i in range(count)]


@pytest.mark.parametrize("count, expected", [(7, False), (8, True)])
def test_nominee_needs_enough_directorships(count, expected):
    stakes, directors = _directed_companies(count, directors_share=2)
    assert ("nominee_director" in rules_for(build(stakes, directors), "C-0")) is expected


def test_a_busy_owner_is_not_a_nominee():
    stakes, directors = _directed_companies(10, directors_share=60)
    assert "nominee_director" not in rules_for(build(stakes, directors), "C-0")


def test_a_director_who_owns_part_of_the_companies_is_not_a_nominee():
    # directs 8 companies, owns 60% of 4 of them and 2% of the other 4: only half are "owns nothing"
    stakes = [("P-1", f"C-{i}", 60 if i < 4 else 2) for i in range(8)]
    stakes += [(f"P-2{i}", f"C-{i}", 40 if i < 4 else 98) for i in range(8)]
    directors = [("P-1", f"C-{i}") for i in range(8)]
    for company in ("C-0", "C-7"):
        assert "nominee_director" not in rules_for(build(stakes, directors), company)


def test_nominee_threshold_for_what_counts_as_owning_nothing():
    stakes = [("P-1", f"C-{i}", 5) for i in range(8)] + [(f"P-2{i}", f"C-{i}", 95) for i in range(8)]
    directors = [("P-1", f"C-{i}") for i in range(8)]
    assert "nominee_director" not in rules_for(build(stakes, directors), "C-0")     # exactly 5% is not "under 5%"


# R5
def test_threshold_dodging_is_flagged_when_routes_add_up_but_none_is_big():
    # P-1 holds 16% directly, 60% x 10% = 6% through C-1 and 50% x 8% = 4% through C-2: 26% in total
    stakes = [("P-1", "C-9", 16), ("P-1", "C-1", 60), ("C-1", "C-9", 10), ("P-1", "C-2", 50), ("C-2", "C-9", 8),
              ("P-2", "C-9", 66), ("P-3", "C-1", 40), ("P-4", "C-2", 50)]
    assert "threshold_dodging" in rules_for(build(stakes), "C-9")


def test_a_single_large_route_is_not_dodging():
    assert "threshold_dodging" not in rules_for(build([("P-1", "C-1", 30), ("P-2", "C-1", 70)]), "C-1")


def test_routes_that_do_not_reach_the_threshold_are_not_dodging():
    stakes = [("P-1", "C-9", 15), ("P-1", "C-1", 60), ("C-1", "C-9", 10), ("P-2", "C-9", 79), ("P-3", "C-1", 40)]
    assert "threshold_dodging" not in rules_for(build(stakes), "C-9")        # 15% + 6% = 21%


# R6
@pytest.mark.parametrize("recorded, expected_points", [(80, 0), (75, 15), (51, 15), (50, 30), (20, 30)])
def test_unresolved_ownership_tiers(recorded, expected_points):
    registry = build([("P-1", "C-1", recorded)])
    finding = analyze(registry).finding("C-1")
    points = sum(f.points for f in finding.flags if f.rule == "unresolved_ownership") if finding else 0
    assert points == expected_points


# R7
@pytest.mark.parametrize("days, expected", [(365, True), (366, False)])
def test_rapid_dissolution_boundary(days, expected):
    start = dt.date(2021, 1, 1)
    registry = build([("P-1", "C-1", 100)], lifetimes={"C-1": (start, start + dt.timedelta(days=days))})
    assert ("rapid_dissolution" in rules_for(registry, "C-1")) is expected


def test_an_active_company_is_never_a_rapid_dissolution():
    assert "rapid_dissolution" not in rules_for(build([("P-1", "C-1", 100)]), "C-1")


# scoring
def test_points_add_up_and_cap_at_100():
    start = dt.date(2021, 1, 1)
    count = 8
    stakes = [("P-1", f"C-{i}", 2) for i in range(count)] + [(f"P-2{i}", f"C-{i}", 40) for i in range(count)]
    directors = [("P-1", f"C-{i}") for i in range(count)]
    registry = build(stakes, directors, address_of={f"C-{i}": "A-shared" for i in range(count)},
                     lifetimes={"C-0": (start, start + dt.timedelta(days=100))})
    finding = analyze(registry).finding("C-0")
    expected = sum(RULES[r].points for r in ("mass_address", "nominee_director", "rapid_dissolution")) + 30
    assert finding.score == min(100, expected)
    assert finding.score <= 100


def test_levels_follow_the_configured_thresholds():
    config = Config()
    assert [level_for(s, config) for s in (0, 24, 25, 49, 50, 100)] == ["low", "low", "medium", "medium", "high", "high"]
    assert level_for(40, Config(high_score=40)) == "high"
