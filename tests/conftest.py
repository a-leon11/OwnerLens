import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ownerlens.registry import Address, Company, Directorship, Person, Registry, Stake  # noqa: E402

DEFAULT_DATE = dt.date(2020, 1, 1)


def build(stakes, directors=(), address_of=None, lifetimes=None):
    """A tiny registry from a list of (owner, company, percent) tuples.

    Every id that appears is created. `address_of` maps a company to an address id
    (default: each company has its own address). `lifetimes` maps a company to
    (incorporated, dissolved).
    """
    address_of = address_of or {}
    lifetimes = lifetimes or {}
    ids = {x for owner, company, _ in stakes for x in (owner, company)}
    ids |= {x for person, company in directors for x in (person, company)}
    ids |= set(address_of) | set(lifetimes)
    persons = {i: Person(i, f"Person {i}") for i in sorted(ids) if i.startswith("P-")}
    company_ids = sorted(i for i in ids if i.startswith("C-"))
    address_ids = {address_of.get(c, f"A-{c}") for c in company_ids}
    addresses = {a: Address(a, f"{a} Test Street", "Testville") for a in address_ids}
    companies = {}
    for c in company_ids:
        incorporated, dissolved = lifetimes.get(c, (DEFAULT_DATE, None))
        companies[c] = Company(c, f"Company {c}", "testing", incorporated, dissolved, address_of.get(c, f"A-{c}"))
    return Registry(
        persons=persons, companies=companies, addresses=addresses,
        stakes=tuple(Stake(o, c, float(p)) for o, c, p in stakes),
        directorships=tuple(Directorship(p, c, "director", DEFAULT_DATE) for p, c in directors),
    )
