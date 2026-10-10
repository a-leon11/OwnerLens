import hashlib

from ownerlens.generate import AS_OF, generate, write_truth
from ownerlens.registry import write_registry


def _fingerprint(directory):
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_the_same_seed_gives_identical_files(tmp_path):
    for name in ("one", "two"):
        registry, truth = generate(7)
        write_registry(registry, tmp_path / name)
        write_truth(truth, tmp_path / name / "truth.json")
    assert _fingerprint(tmp_path / "one") == _fingerprint(tmp_path / "two")


def test_different_seeds_give_different_registries():
    first, _ = generate(7)
    second, _ = generate(8)
    assert [c.legal_name for c in first.companies.values()] != [c.legal_name for c in second.companies.values()]


def test_the_ground_truth_points_at_real_companies():
    registry, truth = generate()
    named = {c for p in truth["patterns"] for c in p["companies"]}
    named |= {c for group in truth["benign"].values() for c in group}
    assert named <= set(registry.companies)
    assert {p["pattern"] for p in truth["patterns"]} == {
        "ownership_ring", "layered_chain", "shell_factory_address", "shell_factory_nominee",
        "shell_factory_closures", "threshold_dodging", "opaque_ownership"}


def test_nothing_happens_after_the_reference_date():
    registry, _ = generate()
    assert all(c.incorporated <= AS_OF for c in registry.companies.values())
    assert all(c.dissolved is None or c.dissolved <= AS_OF for c in registry.companies.values())


def test_ids_do_not_reveal_which_companies_were_planted():
    registry, truth = generate()
    planted = sorted(c for p in truth["patterns"] for c in p["companies"])
    numbers = [int(c[2:]) for c in planted]
    assert min(numbers) < len(registry.companies) / 2 < max(numbers)   # spread over the range, not clustered at the end


def test_only_the_designed_structures_are_crowded():
    registry, truth = generate()
    from collections import Counter
    crowded = [n for n in Counter(c.address_id for c in registry.companies.values()).values() if n >= 4]
    assert sorted(crowded) == [9, 12]            # the transparent group and the shell factory


def test_ordinary_companies_are_never_deeply_layered():
    from ownerlens.ownership import Ownership

    for seed in range(7, 13):
        registry, truth = generate(seed)
        planted = {c for p in truth["patterns"] for c in p["companies"]}
        own = Ownership(registry)
        for company_id in registry.companies:
            if company_id in planted:
                continue
            deepest = max((r.intermediaries for h in own.holdings[company_id] for r in h.routes), default=0)
            assert deepest <= 2, (seed, company_id, deepest)
