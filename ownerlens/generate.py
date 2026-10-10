"""A deterministic generator for a FICTIONAL company registry.

Every person, company and address is invented from word lists. Nothing here is derived
from a real registry, and any resemblance to a real name is a coincidence.

The registry has three kinds of content:

  * background: ordinary companies with ordinary ownership, so that the red-flag rules
    have realistic noise to work against (including a few harmless oddities).
  * benign lookalikes: structures that resemble something suspicious but are normal,
    to check that the rules do not over-fire.
  * planted structures: known suspicious patterns. The generator records them in a
    ground-truth file so the detection can be measured against what was planted.

Only random.Random().random() is used (the one method Python promises never to change),
so the output is identical on every machine and Python version. At the end all ids are
shuffled, so the order of the ids gives nothing away.
"""
from __future__ import annotations

import datetime as dt
import random
from collections import Counter
from dataclasses import dataclass, field

from .registry import Address, Company, Directorship, Person, Registry, Stake, is_person

SEED = 7
AS_OF = dt.date(2026, 1, 1)
N_BACKGROUND = 320

FIRST = ["Alma", "Bruno", "Carla", "Diego", "Elena", "Felix", "Gabriela", "Hector", "Irene", "Javier",
         "Karina", "Luis", "Marta", "Nicolas", "Olivia", "Pablo", "Quinn", "Rosa", "Sergio", "Teresa",
         "Ulises", "Valeria", "Walter", "Ximena", "Yolanda", "Zoe", "Adrian", "Beatriz", "Cesar", "Daniela",
         "Emilio", "Fernanda", "Gustavo", "Helena", "Ivan", "Julia", "Kevin", "Laura", "Mateo", "Nora"]
LAST = ["Alvarez", "Bennett", "Castillo", "Dominguez", "Ellis", "Fischer", "Garza", "Hughes", "Ibarra", "Jensen",
        "Keller", "Lopez", "Morales", "Novak", "Ortega", "Patel", "Quintero", "Reyes", "Silva", "Torres",
        "Underwood", "Vargas", "Walsh", "Xu", "Yates", "Zamora", "Aguilar", "Brooks", "Cordero", "Delgado",
        "Estrada", "Flores", "Guzman", "Herrera", "Iglesias", "Jimenez", "Kovacs", "Leal", "Mendoza", "Navarro"]
PREFIX = ["Northbridge", "Silverline", "Harbor", "Redwood", "Bluepeak", "Ironwood", "Clearwater", "Summit",
          "Oakridge", "Lakeshore", "Stonegate", "Brightfield", "Crestview", "Eastgate", "Fairmont", "Goldleaf",
          "Highland", "Kingsway", "Lighthouse", "Maplewood", "Newport", "Orchard", "Pinecrest", "Riverbend",
          "Sandstone", "Thornfield", "Unity", "Valley", "Westbrook", "Yellowstone", "Alder", "Birch", "Cedar",
          "Dune", "Ember", "Fjord", "Granite", "Hollow", "Island", "Juniper"]
NOUN = ["Logistics", "Trading", "Foods", "Partners", "Capital", "Systems", "Supply", "Consulting", "Holdings",
        "Industries", "Services", "Ventures", "Works", "Solutions", "Distribution", "Labs", "Group", "Materials",
        "Hospitality", "Energy"]
SUFFIX = ["Ltd", "LLC", "Inc", "SA"]
SECTORS = ["logistics", "retail", "software", "food", "construction", "consulting", "manufacturing",
           "hospitality", "energy", "trading"]
STREETS = ["Olive", "Harbor", "Pine", "Market", "Station", "Mill", "Church", "Garden", "Bridge", "Lake", "Hill",
           "River", "Cedar", "Union", "Park"]
STREET_TYPES = ["Street", "Avenue", "Road"]
CITIES = ["Riverton", "Eastfield", "Port Alder", "Lakemont", "Stonebridge", "Westhaven", "Northgate",
          "Cape Merrow", "Fairhaven", "Ashdown"]
TWO_WAY = [(50, 50), (60, 40), (70, 30), (80, 20), (51, 49)]
THREE_WAY = [(50, 30, 20), (40, 40, 20), (34, 33, 33)]


class Rng:
    """Deterministic helpers built on random.random() only."""

    def __init__(self, seed: int) -> None:
        self._r = random.Random(seed)

    def random(self) -> float:
        return self._r.random()

    def chance(self, p: float) -> bool:
        return self.random() < p

    def randint(self, low: int, high: int) -> int:
        return low + int(self.random() * (high - low + 1))

    def choice(self, items):
        return items[int(self.random() * len(items))]

    def shuffled(self, items):
        items = list(items)
        for i in range(len(items) - 1, 0, -1):
            j = self.randint(0, i)
            items[i], items[j] = items[j], items[i]
        return items

    def date_between(self, low: dt.date, high: dt.date) -> dt.date:
        return low + dt.timedelta(days=self.randint(0, (high - low).days))


@dataclass
class Builder:
    """Collects entities with temporary ids; `finish` relabels them in shuffled order."""

    rng: Rng
    persons: dict = field(default_factory=dict)
    companies: dict = field(default_factory=dict)
    addresses: dict = field(default_factory=dict)
    stakes: list = field(default_factory=list)
    directorships: list = field(default_factory=list)
    _names: set = field(default_factory=set)

    def person(self) -> str:
        while True:
            name = f"{self.rng.choice(FIRST)} {self.rng.choice(LAST)}"
            if name not in self._names:
                break
        self._names.add(name)
        pid = f"P-t{len(self.persons) + 1}"
        self.persons[pid] = name
        return pid

    def address(self) -> str:
        aid = f"A-t{len(self.addresses) + 1}"
        street = f"{self.rng.randint(1, 240)} {self.rng.choice(STREETS)} {self.rng.choice(STREET_TYPES)}"
        self.addresses[aid] = (street, self.rng.choice(CITIES))
        return aid

    def company(self, incorporated: dt.date, address: str, dissolved: dt.date | None = None,
                sector: str | None = None) -> str:
        while True:
            name = f"{self.rng.choice(PREFIX)} {self.rng.choice(NOUN)} {self.rng.choice(SUFFIX)}"
            if name not in self._names:
                break
        self._names.add(name)
        cid = f"C-t{len(self.companies) + 1}"
        self.companies[cid] = dict(name=name, sector=sector or self.rng.choice(SECTORS),
                                   incorporated=incorporated, dissolved=dissolved, address=address)
        return cid

    def own(self, owner: str, company: str, percent: float) -> None:
        self.stakes.append((owner, company, percent))

    def direct(self, person: str, company: str, role: str = "director") -> None:
        self.directorships.append((person, company, role, self.companies[company]["incorporated"]))


def _background(b: Builder, n: int) -> dict:
    """Ordinary companies. Returns bookkeeping that the lookalike step reuses."""
    rng = b.rng
    usage: Counter = Counter()          # how many companies a background person is tied to
    reusable: list[str] = []            # persons that can be reused (usage below the cap)
    layer: dict[str, int] = {}          # intermediaries between the top owner and the company
    parents: list[str] = []             # companies that can own another company
    open_addresses: list[str] = []      # small shared addresses with room for one more tenant
    tenants: Counter = Counter()
    ids: list[str] = []

    def pick_person(exclude: set[str]) -> str:
        candidates = [p for p in reusable if usage[p] < 4 and p not in exclude]
        if candidates and rng.chance(0.25):
            chosen = rng.choice(candidates)
        else:
            chosen = b.person()
            reusable.append(chosen)
        usage[chosen] += 1
        return chosen

    for _ in range(n):
        incorporated = rng.date_between(dt.date(2008, 1, 1), dt.date(2024, 6, 30))

        parent = None
        if parents and rng.chance(0.06):
            parent = rng.choice(parents)
            incorporated = max(incorporated, b.companies[parent]["incorporated"] + dt.timedelta(days=60))

        if open_addresses and rng.chance(0.15):
            address = rng.choice(open_addresses)
        else:
            address = b.address()
        tenants[address] += 1
        if tenants[address] < 3 and address not in open_addresses:
            open_addresses.append(address)
        if tenants[address] >= 3 and address in open_addresses:
            open_addresses.remove(address)

        dissolved = None
        roll = rng.random()
        if roll < 0.015 and incorporated < AS_OF - dt.timedelta(days=500):
            dissolved = incorporated + dt.timedelta(days=rng.randint(120, 330))      # harmless short life
        elif roll < 0.07 and incorporated < AS_OF - dt.timedelta(days=2200):
            dissolved = incorporated + dt.timedelta(days=rng.randint(365, 2100))

        company = b.company(incorporated, address, dissolved)
        ids.append(company)

        owners: list[str] = []
        if parent:
            layer[company] = layer[parent] + 1
            if rng.chance(0.5):
                b.own(parent, company, 100)
            else:
                person = pick_person({p for p, c, _ in b.stakes if c == parent})
                owners.append(person)
                b.own(parent, company, 60)
                b.own(person, company, 40)
        else:
            layer[company] = 0
            roll = rng.random()
            split = (100,) if roll < 0.55 else rng.choice(TWO_WAY) if roll < 0.90 else rng.choice(THREE_WAY)
            for share in split:
                person = pick_person(set(owners))
                owners.append(person)
                b.own(person, company, share)

        if owners:
            managers = owners[:2] if rng.chance(0.4) else owners[:1]
        else:
            managers = [pick_person(set())]
        for role_index, person in enumerate(managers):
            b.direct(person, company, "director" if role_index == 0 else "legal_representative")

        if dissolved is None and layer[company] <= 1:
            parents.append(company)
    return {"ids": ids}


def _benign(b: Builder, truth: dict) -> None:
    """Structures that look a little like red flags but are ordinary."""
    rng = b.rng
    benign = truth["benign"]

    # 1. A transparent corporate group: a holding and eight subsidiaries at one head office.
    #    Mass address is the only thing that should fire.
    owners = [b.person() for _ in range(3)]
    head_office = b.address()
    holding = b.company(dt.date(2012, 3, 1), head_office, sector="holding")
    for owner, share in zip(owners, (40, 35, 25)):
        b.own(owner, holding, share)
    b.direct(owners[0], holding)
    group = [holding]
    for _ in range(8):
        subsidiary = b.company(rng.date_between(dt.date(2013, 1, 1), dt.date(2020, 12, 31)), head_office)
        b.own(holding, subsidiary, 100)
        b.direct(owners[rng.randint(0, 2)], subsidiary)
        group.append(subsidiary)
    benign["transparent_group"] = group

    # 2. A busy operator who directs ten companies and owns most of each one.
    #    Many directorships alone are not a sign of a nominee.
    operator = b.person()
    busy = []
    for _ in range(10):
        company = b.company(rng.date_between(dt.date(2010, 1, 1), dt.date(2022, 12, 31)), b.address())
        b.own(operator, company, 60)
        b.own(b.person(), company, 40)
        b.direct(operator, company)
        busy.append(company)
    benign["busy_operator"] = busy

    # 3. A legitimate three-company chain (two intermediaries is normal).
    top = b.person()
    first = b.company(dt.date(2011, 5, 1), b.address())
    second = b.company(dt.date(2014, 8, 1), b.address())
    third = b.company(dt.date(2018, 2, 1), b.address())
    b.own(top, first, 100)
    b.own(first, second, 100)
    b.own(second, third, 100)
    for company in (first, second, third):
        b.direct(top, company)
    benign["short_chain"] = [first, second, third]

    # 4. Two ordinary companies that happened to close within a year.
    short_lived = []
    for start in (dt.date(2021, 4, 12), dt.date(2022, 9, 5)):
        company = b.company(start, b.address(), dissolved=start + dt.timedelta(days=270))
        owner = b.person()
        b.own(owner, company, 100)
        b.direct(owner, company)
        short_lived.append(company)
    benign["short_lived"] = short_lived


def _planted(b: Builder, truth: dict) -> None:
    rng = b.rng
    patterns = truth["patterns"]

    def pattern(name: str, rule: str, companies: list[str], note: str) -> None:
        patterns.append({"pattern": name, "rule": rule, "companies": companies, "note": note})

    # P1. A ring of cross-holdings: A owns B, B owns C, C owns A.
    ring = [b.company(rng.date_between(dt.date(2015, 1, 1), dt.date(2019, 12, 31)), b.address()) for _ in range(3)]
    for index, company in enumerate(ring):
        b.own(ring[(index - 1) % 3], company, 45)   # previous company in the ring owns 45%
        outsider = b.person()
        b.own(outsider, company, 55)
        b.direct(outsider, company)
    pattern("ownership_ring", "circular_ownership", ring, "three companies that own each other in a circle")

    # P2. A five-company chain between one person and the last company.
    chain_owner = b.person()
    chain = [b.company(dt.date(2016 + i, 3, 1), b.address()) for i in range(5)]
    b.own(chain_owner, chain[0], 100)
    for upper, lower in zip(chain, chain[1:]):
        b.own(upper, lower, 100)
    agent = b.person()
    for company in chain:
        b.direct(agent, company)
    pattern("layered_chain", "layering", chain[3:], "one person reaches the last two companies through 3 and 4 intermediaries")

    # P3. A shell factory: twelve companies, one address, one director who owns nothing.
    address = b.address()
    nominee = b.person()
    owners = [b.person() for _ in range(4)]
    shells = []
    window_start = dt.date(2024, 3, 1)
    for index in range(12):
        company = b.company(window_start + dt.timedelta(days=rng.randint(0, 45)), address, sector="consulting")
        b.own(owners[index % 4], company, 100)
        b.direct(nominee, company)
        shells.append(company)
    closed = shells[:5]
    for company in closed:
        b.companies[company]["dissolved"] = b.companies[company]["incorporated"] + dt.timedelta(days=rng.randint(150, 300))
    pattern("shell_factory_address", "mass_address", shells, "twelve companies registered at one address")
    pattern("shell_factory_nominee", "nominee_director", shells, "one person directs all twelve and owns none")
    pattern("shell_factory_closures", "rapid_dissolution", closed, "five of the twelve closed within a year")

    # P4. Threshold dodging: 16% direct plus 6% and 4% through two companies = 26% in total.
    target = b.company(dt.date(2017, 6, 1), b.address())
    y = b.person()
    others = [b.person() for _ in range(4)]
    mid_one = b.company(dt.date(2017, 1, 15), b.address())
    mid_two = b.company(dt.date(2017, 2, 20), b.address())
    b.own(y, mid_one, 60)
    b.own(others[0], mid_one, 40)
    b.own(y, mid_two, 50)
    b.own(others[1], mid_two, 50)
    b.own(y, target, 16)
    b.own(mid_one, target, 10)
    b.own(mid_two, target, 8)
    b.own(others[2], target, 40)
    b.own(others[3], target, 26)
    for company, person in ((target, others[2]), (mid_one, others[0]), (mid_two, others[1])):
        b.direct(person, company)
    pattern("threshold_dodging", "threshold_dodging", [target], "one person holds 26% in total, but never more than 16% by any one route")

    # P5. Opaque ownership: stakes that cannot be traced to a person.
    unknown_holder = b.company(dt.date(2019, 4, 1), b.address())        # a company with no recorded owner
    opaque = []
    first = b.company(dt.date(2018, 7, 1), b.address())                 # only 20% recorded
    p = b.person()
    b.own(p, first, 20)
    b.direct(p, first)
    second = b.company(dt.date(2019, 9, 1), b.address())                # 100% held by the unknown company
    b.own(unknown_holder, second, 100)
    b.direct(b.person(), second)
    third = b.company(dt.date(2020, 1, 20), b.address())                # half unknown, half a person
    b.own(unknown_holder, third, 50)
    p = b.person()
    b.own(p, third, 50)
    b.direct(p, third)
    fourth = b.company(dt.date(2021, 5, 3), b.address())                # 30% unrecorded
    p = b.person()
    b.own(p, fourth, 70)
    b.direct(p, fourth)
    b.direct(b.person(), unknown_holder)
    opaque = [first, second, third, fourth, unknown_holder]
    pattern("opaque_ownership", "unresolved_ownership", opaque, "stakes that end in a company with no recorded owner, or that are not recorded at all")


def _finish(b: Builder, truth: dict) -> tuple[Registry, dict]:
    """Relabel everything with shuffled ids and build the final Registry and ground truth."""
    rng = b.rng

    def relabel(old_ids: list[str], prefix: str, width: int) -> dict[str, str]:
        order = rng.shuffled(range(1, len(old_ids) + 1))
        return {old: f"{prefix}-{number:0{width}d}" for old, number in zip(old_ids, order)}

    person_map = relabel(list(b.persons), "P", 4)
    company_map = relabel(list(b.companies), "C", 4)
    address_map = relabel(list(b.addresses), "A", 3)
    entity_map = {**person_map, **company_map}

    persons = {person_map[k]: Person(person_map[k], name) for k, name in b.persons.items()}
    addresses = {address_map[k]: Address(address_map[k], street, city) for k, (street, city) in b.addresses.items()}
    companies = {}
    for key, c in b.companies.items():
        new = company_map[key]
        companies[new] = Company(new, c["name"], c["sector"], c["incorporated"], c["dissolved"], address_map[c["address"]])
    stakes = tuple(Stake(entity_map[o], company_map[c], float(p)) for o, c, p in b.stakes)
    directorships = tuple(Directorship(person_map[p], company_map[c], role, since)
                          for p, c, role, since in b.directorships)

    final_truth = {
        "seed": truth["seed"],
        "as_of": AS_OF.isoformat(),
        "patterns": [{**p, "companies": sorted(company_map[c] for c in p["companies"])} for p in truth["patterns"]],
        "benign": {k: sorted(company_map[c] for c in v) for k, v in truth["benign"].items()},
    }
    return Registry(persons, companies, addresses, stakes, directorships), final_truth


def check_invariants(registry: Registry) -> None:
    """Fail loudly if the generator produced something it should not have."""
    from .registry import validate
    problems = validate(registry)
    assert not problems, problems
    assert all(c.dissolved is None or c.dissolved <= AS_OF for c in registry.companies.values())
    assert all(c.incorporated <= AS_OF for c in registry.companies.values())
    assert len({c.legal_name for c in registry.companies.values()}) == len(registry.companies)
    for company_id in registry.companies:
        total = sum(s.percent for s in registry.stakes if s.company_id == company_id)
        assert total <= 100.0001, (company_id, total)
    assert all(is_person(p) for p in registry.persons)


def generate(seed: int = SEED, n_background: int = N_BACKGROUND) -> tuple[Registry, dict]:
    """Build the registry and its ground truth. The same seed always gives the same result."""
    b = Builder(Rng(seed))
    truth = {"seed": seed, "patterns": [], "benign": {}}
    _background(b, n_background)
    _benign(b, truth)
    _planted(b, truth)
    registry, final_truth = _finish(b, truth)
    check_invariants(registry)
    return registry, final_truth


def write_truth(truth: dict, path) -> None:
    """Save the ground truth (what was planted) next to the registry files."""
    import json
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(truth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
