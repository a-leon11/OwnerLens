import csv

import pytest

from conftest import build
from ownerlens.generate import generate
from ownerlens.registry import RegistryError, load_registry, validate, write_registry


def test_round_trip_keeps_everything(tmp_path):
    registry, _ = generate()
    write_registry(registry, tmp_path)
    loaded = load_registry(tmp_path)
    assert loaded.companies == registry.companies
    assert loaded.persons == registry.persons
    assert loaded.addresses == registry.addresses
    assert set(loaded.stakes) == set(registry.stakes)
    assert set(loaded.directorships) == set(registry.directorships)


def test_a_clean_registry_has_no_problems():
    assert validate(build([("P-1", "C-1", 100)])) == []


@pytest.mark.parametrize("stakes, text", [
    ([("P-1", "C-1", 60), ("P-2", "C-1", 50)], "add up to"),
    ([("P-1", "C-1", 0)], "percent"),
    ([("P-1", "C-1", 101)], "percent"),
    ([("C-1", "C-1", 50)], "owns itself"),
    ([("P-1", "C-1", 50), ("P-1", "C-1", 20)], "listed twice"),
])
def test_bad_ownership_is_reported(stakes, text):
    problems = validate(build(stakes))
    assert any(text in p for p in problems), problems


def test_unknown_references_are_reported():
    registry = build([("P-1", "C-1", 100)])
    broken = type(registry)(registry.persons, registry.companies, registry.addresses,
                            registry.stakes + (type(registry.stakes[0])("P-404", "C-1", 0.5),), registry.directorships)
    assert any("unknown owner P-404" in p for p in validate(broken))


def test_dissolved_before_incorporated_is_reported():
    import datetime as dt
    registry = build([("P-1", "C-1", 100)], lifetimes={"C-1": (dt.date(2020, 5, 1), dt.date(2020, 1, 1))})
    assert any("dissolved before" in p for p in validate(registry))


def test_missing_file_and_column(tmp_path):
    registry, _ = generate()
    write_registry(registry, tmp_path)
    (tmp_path / "directors.csv").unlink()
    with pytest.raises(RegistryError, match="missing file"):
        load_registry(tmp_path)

    write_registry(registry, tmp_path)
    with (tmp_path / "ownership.csv").open("w", newline="") as handle:
        csv.writer(handle).writerow(["owner_id", "company_id"])
    with pytest.raises(RegistryError, match="missing column"):
        load_registry(tmp_path)


def test_a_bad_value_gives_a_registry_error_not_a_traceback(tmp_path):
    registry, _ = generate()
    write_registry(registry, tmp_path)
    text = (tmp_path / "ownership.csv").read_text().splitlines()
    text[1] = text[1].rsplit(",", 1)[0] + ",not-a-number"
    (tmp_path / "ownership.csv").write_text("\n".join(text) + "\n")
    with pytest.raises(RegistryError, match="could not read"):
        load_registry(tmp_path)
