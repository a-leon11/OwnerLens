"""The registry data model: companies, people, addresses, ownership and directors.

The model mirrors the kind of fields a public company registry exposes about legal
entities. It keeps the personal data to a minimum on purpose: a person has an id and a
name, nothing else.

Data lives in five CSV files, so any registry export can be mapped onto it:

    persons.csv     person_id, full_name
    companies.csv   company_id, legal_name, sector, incorporated, dissolved, address_id
    addresses.csv   address_id, street, city
    ownership.csv   owner_id, company_id, percent
    directors.csv   person_id, company_id, role, since

Ids starting with "P-" are people, ids starting with "C-" are companies. An owner in
ownership.csv can be either, which is how ownership chains are expressed.
"""
from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

FILES = ("persons.csv", "companies.csv", "addresses.csv", "ownership.csv", "directors.csv")
TOLERANCE = 0.01  # percentage points allowed when checking that owners add up to 100


class RegistryError(ValueError):
    """The registry data is unusable (missing file or column, or invalid references)."""


@dataclass(frozen=True)
class Person:
    person_id: str
    full_name: str


@dataclass(frozen=True)
class Address:
    address_id: str
    street: str
    city: str


@dataclass(frozen=True)
class Company:
    company_id: str
    legal_name: str
    sector: str
    incorporated: dt.date
    dissolved: dt.date | None
    address_id: str


@dataclass(frozen=True)
class Stake:
    """`owner_id` holds `percent` per cent of `company_id`."""

    owner_id: str
    company_id: str
    percent: float


@dataclass(frozen=True)
class Directorship:
    person_id: str
    company_id: str
    role: str
    since: dt.date


@dataclass(frozen=True)
class Registry:
    persons: dict[str, Person]
    companies: dict[str, Company]
    addresses: dict[str, Address]
    stakes: tuple[Stake, ...]
    directorships: tuple[Directorship, ...]


def is_person(entity_id: str) -> bool:
    return entity_id.startswith("P-")


def _date(text: str) -> dt.date | None:
    text = text.strip()
    return dt.date.fromisoformat(text) if text else None


def _rows(directory: Path, name: str, columns: tuple[str, ...]) -> list[dict[str, str]]:
    path = directory / name
    if not path.exists():
        raise RegistryError(f"missing file: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in columns if c not in (reader.fieldnames or [])]
        if missing:
            raise RegistryError(f"{name}: missing column(s) {', '.join(missing)}")
        return list(reader)


def load_registry(directory: str | Path) -> Registry:
    """Read the five CSV files and check them. Raises RegistryError on any error."""
    directory = Path(directory)
    try:
        persons = {r["person_id"]: Person(r["person_id"], r["full_name"])
                   for r in _rows(directory, "persons.csv", ("person_id", "full_name"))}
        addresses = {r["address_id"]: Address(r["address_id"], r["street"], r["city"])
                     for r in _rows(directory, "addresses.csv", ("address_id", "street", "city"))}
        companies = {r["company_id"]: Company(r["company_id"], r["legal_name"], r["sector"],
                                              _date(r["incorporated"]), _date(r["dissolved"]), r["address_id"])
                     for r in _rows(directory, "companies.csv",
                                    ("company_id", "legal_name", "sector", "incorporated", "dissolved", "address_id"))}
        stakes = tuple(Stake(r["owner_id"], r["company_id"], float(r["percent"]))
                       for r in _rows(directory, "ownership.csv", ("owner_id", "company_id", "percent")))
        directorships = tuple(Directorship(r["person_id"], r["company_id"], r["role"], _date(r["since"]))
                              for r in _rows(directory, "directors.csv", ("person_id", "company_id", "role", "since")))
    except (ValueError, TypeError) as error:
        if isinstance(error, RegistryError):
            raise
        raise RegistryError(f"could not read the registry: {error}") from error

    registry = Registry(persons, companies, addresses, stakes, directorships)
    problems = validate(registry)
    if problems:
        raise RegistryError("invalid registry:\n  " + "\n  ".join(problems))
    return registry


def validate(registry: Registry) -> list[str]:
    """Return a list of human-readable problems (an empty list means the data is usable)."""
    problems: list[str] = []
    for company in registry.companies.values():
        if company.address_id not in registry.addresses:
            problems.append(f"{company.company_id}: unknown address {company.address_id}")
        if company.dissolved and company.dissolved < company.incorporated:
            problems.append(f"{company.company_id}: dissolved before it was incorporated")

    totals: dict[str, float] = {}
    seen: set[tuple[str, str]] = set()
    for stake in registry.stakes:
        known_owner = stake.owner_id in (registry.persons if is_person(stake.owner_id) else registry.companies)
        if not known_owner:
            problems.append(f"ownership: unknown owner {stake.owner_id}")
        if stake.company_id not in registry.companies:
            problems.append(f"ownership: unknown company {stake.company_id}")
        if stake.owner_id == stake.company_id:
            problems.append(f"ownership: {stake.company_id} owns itself")
        if not 0 < stake.percent <= 100:
            problems.append(f"ownership: {stake.owner_id} -> {stake.company_id} has percent {stake.percent}")
        if (stake.owner_id, stake.company_id) in seen:
            problems.append(f"ownership: {stake.owner_id} -> {stake.company_id} listed twice")
        seen.add((stake.owner_id, stake.company_id))
        totals[stake.company_id] = totals.get(stake.company_id, 0.0) + stake.percent
    for company_id, total in totals.items():
        if total > 100 + TOLERANCE:
            problems.append(f"ownership: owners of {company_id} add up to {total:.2f}%")

    for director in registry.directorships:
        if director.person_id not in registry.persons:
            problems.append(f"directors: unknown person {director.person_id}")
        if director.company_id not in registry.companies:
            problems.append(f"directors: unknown company {director.company_id}")
    return problems


def write_registry(registry: Registry, directory: str | Path) -> None:
    """Write the five CSV files (rows sorted by id, so the output is stable)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    def write(name: str, header: list[str], rows: list[list[object]]) -> None:
        with (directory / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)

    write("persons.csv", ["person_id", "full_name"],
          [[p.person_id, p.full_name] for p in sorted(registry.persons.values(), key=lambda p: p.person_id)])
    write("addresses.csv", ["address_id", "street", "city"],
          [[a.address_id, a.street, a.city] for a in sorted(registry.addresses.values(), key=lambda a: a.address_id)])
    write("companies.csv", ["company_id", "legal_name", "sector", "incorporated", "dissolved", "address_id"],
          [[c.company_id, c.legal_name, c.sector, c.incorporated.isoformat(),
            c.dissolved.isoformat() if c.dissolved else "", c.address_id]
           for c in sorted(registry.companies.values(), key=lambda c: c.company_id)])
    write("ownership.csv", ["owner_id", "company_id", "percent"],
          [[s.owner_id, s.company_id, f"{s.percent:g}"]
           for s in sorted(registry.stakes, key=lambda s: (s.company_id, s.owner_id))])
    write("directors.csv", ["person_id", "company_id", "role", "since"],
          [[d.person_id, d.company_id, d.role, d.since.isoformat()]
           for d in sorted(registry.directorships, key=lambda d: (d.company_id, d.person_id))])
