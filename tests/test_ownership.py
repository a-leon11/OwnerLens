import pytest

from conftest import build
from ownerlens.ownership import Ownership


def test_a_two_layer_chain_multiplies_the_percentages():
    own = Ownership(build([("P-1", "C-1", 50), ("C-1", "C-2", 40)]))
    assert own.effective_stake("P-1", "C-2") == pytest.approx(0.20)
    assert own.effective_stake("P-1", "C-1") == pytest.approx(0.50)


def test_several_routes_are_added_up():
    own = Ownership(build([("P-1", "C-1", 50), ("C-1", "C-2", 40), ("P-1", "C-2", 30)]))
    holding = own.holdings["C-2"][0]
    assert holding.person_id == "P-1"
    assert len(holding.routes) == 2
    assert holding.effective == pytest.approx(0.50)
    assert sorted(r.intermediaries for r in holding.routes) == [0, 1]


def test_the_beneficial_owner_threshold_includes_the_boundary():
    own = Ownership(build([("P-1", "C-1", 25), ("P-2", "C-1", 24.99), ("P-3", "C-1", 50.01)]))
    owners = {h.person_id for h in own.beneficial_owners("C-1")}
    assert owners == {"P-1", "P-3"}


def test_the_threshold_can_be_changed():
    own = Ownership(build([("P-1", "C-1", 10), ("P-2", "C-1", 90)]))
    assert {h.person_id for h in own.beneficial_owners("C-1", threshold=0.10)} == {"P-1", "P-2"}


def test_unrecorded_shares_are_unresolved():
    own = Ownership(build([("P-1", "C-1", 60)]))
    assert own.unresolved("C-1") == pytest.approx(0.40)


def test_a_company_with_no_owner_at_all_is_fully_unresolved():
    own = Ownership(build([("C-1", "C-2", 100)]))
    assert own.holdings["C-2"] == []
    assert own.unresolved("C-2") == pytest.approx(1.0)


def test_a_fully_owned_chain_is_fully_resolved():
    own = Ownership(build([("P-1", "C-1", 100), ("C-1", "C-2", 100)]))
    assert own.unresolved("C-2") == 0.0


def test_loops_are_found_and_do_not_hang():
    stakes = [("C-1", "C-2", 45), ("C-2", "C-3", 45), ("C-3", "C-1", 45),
              ("P-1", "C-1", 55), ("P-2", "C-2", 55), ("P-3", "C-3", 55)]
    own = Ownership(build(stakes))
    assert own.loops == [["C-1", "C-2", "C-3"]]
    assert own.loop_path(own.loops[0]) == ["C-1", "C-2", "C-3", "C-1"]     # always starts at the smallest id
    # each route may visit a company only once, so what is lost in the loop shows up as unresolved
    assert 0 < own.unresolved("C-1") < 0.25


def test_a_route_never_visits_a_company_twice():
    # C-1 is owned 60% by P-1 and 40% by C-2; C-2 is owned 50% by C-1 and 50% by P-2
    own = Ownership(build([("P-1", "C-1", 60), ("C-2", "C-1", 40), ("C-1", "C-2", 50), ("P-2", "C-2", 50)]))
    for holdings in own.holdings.values():
        for holding in holdings:
            assert all(len(set(route.nodes)) == len(route.nodes) for route in holding.routes)
    assert own.effective_stake("P-1", "C-1") == pytest.approx(0.60)
    assert own.effective_stake("P-2", "C-1") == pytest.approx(0.40 * 0.50)
    assert own.unresolved("C-1") == pytest.approx(0.20)


def test_no_loops_in_a_plain_chain():
    assert Ownership(build([("P-1", "C-1", 100), ("C-1", "C-2", 100)])).loops == []


def test_depth_limit_drops_far_routes():
    stakes = [("P-1", "C-1", 100)] + [(f"C-{i}", f"C-{i + 1}", 100) for i in range(1, 6)]
    own = Ownership(build(stakes), max_depth=3)
    assert own.holdings["C-6"] == []
    assert own.unresolved("C-6") == pytest.approx(1.0)


def test_explain_mentions_routes_and_beneficial_owners():
    text = Ownership(build([("P-1", "C-1", 50), ("C-1", "C-2", 100)])).explain("C-2")
    assert "P-1 > C-1 > C-2" in text and "beneficial owner" in text and "50.0%" in text
