"""Reference data: ERP catalog, CRM customers and e-commerce accounts.

These are the "who" and the "what" of the business. Orders (the "when" and the
"how much") are generated from them later.

The generator produces CLEAN data. The planned data quality issues (Q1-Q12)
are injected afterwards, in a separate step, so that each issue stays explicit
and measurable.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from faker import Faker

from data_generator.catalog import (
    BRANDS,
    CATALOG,
    CRM_SEGMENT_WEIGHTS,
    CRM_SEGMENTS,
    EMAIL_DOMAINS,
    STYLES,
    LeafCategory,
    ParentCategory,
)
from data_generator.config import LOCAL_TZ, GeneratorConfig
from data_generator.records import (
    CrmContact,
    CrmCustomer,
    Customer,
    Product,
    ProductCategory,
    ProductCost,
)
from data_generator.timeutils import as_local_naive, as_utc, random_between

CENT = Decimal("0.01")
# The business existed before the simulated history: catalog and early customers are older.
PRE_HISTORY = timedelta(days=3 * 365)


# ==========================================================================
# ERP: categories, products, cost history
# ==========================================================================


@dataclass
class ErpData:
    categories: list[ProductCategory]
    products: list[Product]
    costs: list[ProductCost]


def generate_erp(cfg: GeneratorConfig) -> ErpData:
    rng = cfg.rng("erp")
    catalog_start = cfg.window_start - PRE_HISTORY
    catalog_created = as_local_naive(catalog_start.replace(hour=9))

    # Two-level hierarchy: parents get ids 1-8, leaves 9-40.
    categories: list[ProductCategory] = [
        ProductCategory(i, p.code, p.name, None, catalog_created, catalog_created)
        for i, p in enumerate(CATALOG, start=1)
    ]
    leaves: list[tuple[int, ParentCategory, LeafCategory]] = []
    for parent_id, parent in enumerate(CATALOG, start=1):
        for leaf in parent.leaves:
            category_id = len(categories) + 1
            categories.append(
                ProductCategory(
                    category_id, leaf.code, leaf.name, parent_id, catalog_created, catalog_created
                )
            )
            leaves.append((category_id, parent, leaf))

    products: list[Product] = []
    costs: list[ProductCost] = []
    for product_id in range(1, cfg.volumes.products + 1):
        category_id, parent, leaf = rng.choice(leaves)
        launched = _launch_moment(rng, cfg, catalog_start)
        product = Product(
            product_id=product_id,
            sku=f"CK-{1000 + product_id}",
            product_name=f"{rng.choice(STYLES)} {rng.choice(parent.materials)} {leaf.noun}",
            category_id=category_id,
            brand=rng.choice(BRANDS),
            list_price=_list_price(rng, leaf),
            is_active=True,
            created_at=as_local_naive(launched),
            updated_at=as_local_naive(launched),
        )
        _apply_product_lifecycle(rng, cfg, product, launched)
        products.append(product)
        costs.extend(_cost_history(rng, cfg, product, parent, launched, len(costs) + 1))

    return ErpData(categories, products, costs)


def _launch_moment(rng: random.Random, cfg: GeneratorConfig, catalog_start: datetime) -> datetime:
    """85% of products predate the history; the rest are launched during it."""
    if rng.random() < 0.85:
        return random_between(rng, catalog_start, cfg.window_start)
    return random_between(rng, cfg.window_start, cfg.window_end - timedelta(days=60))


def _list_price(rng: random.Random, leaf: LeafCategory) -> Decimal:
    """Log-uniform price within the leaf range: more cheap items than expensive ones."""
    value = math.exp(rng.uniform(math.log(leaf.price_low), math.log(leaf.price_high)))
    return Decimal(int(value)) + Decimal("0.99")


def _apply_product_lifecycle(
    rng: random.Random, cfg: GeneratorConfig, product: Product, launched: datetime
) -> None:
    """Changes after launch. The source only keeps the current state and its updated_at."""
    roll = rng.random()
    earliest_change = launched + timedelta(days=90)
    if roll < 0.08 and earliest_change < cfg.window_end:
        # Discontinued: not sold after updated_at
        product.is_active = False
        product.updated_at = as_local_naive(random_between(rng, earliest_change, cfg.window_end))
    elif roll < 0.33:
        # Recent list price change: list_price already holds the new value
        start = max(launched, cfg.window_end - timedelta(days=180))
        product.updated_at = as_local_naive(random_between(rng, start, cfg.window_end))


REVISION_COUNTS = (0, 1, 2, 3, 4)
REVISION_WEIGHTS = (25, 30, 25, 15, 5)


def _cost_history(
    rng: random.Random,
    cfg: GeneratorConfig,
    product: Product,
    parent: ParentCategory,
    launched: datetime,
    first_cost_id: int,
) -> list[ProductCost]:
    """Standard-cost periods: [valid_from, valid_to), exactly one open row per product."""
    first_day = launched.astimezone(LOCAL_TZ).date()
    earliest = max(first_day + timedelta(days=30), cfg.history_start - timedelta(days=365))
    span = (cfg.anchor_date - earliest).days
    wanted = rng.choices(REVISION_COUNTS, REVISION_WEIGHTS)[0]
    n_revisions = min(wanted, max(span, 0))
    revision_days = sorted(
        earliest + timedelta(days=offset) for offset in rng.sample(range(max(span, 0)), n_revisions)
    )

    # The current cost follows the current list price; earlier costs are derived backwards.
    current = float(product.list_price) * parent.cost_ratio * rng.uniform(0.85, 1.15)
    values = [current]
    for factor in [rng.uniform(0.97, 1.10) for _ in revision_days]:
        values.insert(0, values[0] / factor)

    starts: list[date] = [first_day, *revision_days]
    ends: list[date | None] = [*revision_days, None]
    rows: list[ProductCost] = []
    for i, (valid_from, valid_to, value) in enumerate(zip(starts, ends, values, strict=True)):
        created = launched if i == 0 else _business_moment(rng, valid_from)
        rows.append(
            ProductCost(
                cost_id=first_cost_id + i,
                product_id=product.product_id,
                unit_cost=Decimal(value).quantize(CENT),
                valid_from=valid_from,
                valid_to=valid_to,
                created_at=as_local_naive(created),
                updated_at=as_local_naive(created),
            )
        )
    # Closing a period is an UPDATE: it happens when the next period is created.
    for previous, following in zip(rows, rows[1:], strict=False):
        previous.updated_at = following.created_at
    return rows


def _business_moment(rng: random.Random, day: date) -> datetime:
    """Random moment between 08:00 and 18:00 local time."""
    return datetime.combine(day, time(8), LOCAL_TZ) + timedelta(seconds=rng.randrange(10 * 3600))


# ==========================================================================
# Customers: e-commerce accounts and CRM records (with contacts)
# ==========================================================================


@dataclass
class CustomerData:
    crm_customers: list[CrmCustomer]
    crm_contacts: list[CrmContact]
    ecommerce_customers: list[Customer]


@dataclass
class _Person:
    """A real-world person, before being recorded by one or both systems."""

    first_name: str
    last_name: str
    email: str
    phone: str
    signup: datetime | None  # e-commerce account creation; None = CRM-only lead
    crm_created: datetime | None = None  # None = not in the CRM
    crm_id: str | None = None


def generate_customers(cfg: GeneratorConfig) -> CustomerData:
    rng = cfg.rng("customers")
    fake = Faker("en_US")
    fake.seed_instance(rng.getrandbits(64))
    emails = EmailFactory(rng)
    volumes = cfg.volumes
    pre_history_start = cfg.window_start - PRE_HISTORY
    last_moment = cfg.window_end - timedelta(seconds=1)

    # 1. Online customers. Ids follow account creation order, as in a real system.
    online: list[_Person] = []
    for _ in range(volumes.ecommerce_customers):
        first, last = fake.first_name(), fake.last_name()
        signup = _signup_moment(rng, cfg, pre_history_start)
        online.append(_Person(first, last, emails.new(first, last), random_phone(rng), signup))
    online.sort(key=lambda person: person.signup)

    # 2. Most online customers also exist in the CRM, before or after their signup.
    for person in online:
        if rng.random() >= volumes.crm_linked_share:
            continue
        if rng.random() < 0.6:  # known before buying online (store visit, phone order)
            person.crm_created = person.signup - timedelta(seconds=rng.randrange(400 * 86_400))
        else:  # registered in the CRM after the first online purchase
            later = person.signup + timedelta(seconds=rng.randrange(1, 60 * 86_400))
            person.crm_created = min(later, last_moment)

    # 3. CRM-only leads: never bought online, not part of the sales analysis.
    leads: list[_Person] = []
    for _ in range(volumes.crm_leads):
        first, last = fake.first_name(), fake.last_name()
        created = random_between(rng, pre_history_start, cfg.window_end)
        leads.append(
            _Person(first, last, emails.new(first, last), random_phone(rng), None, created)
        )

    # 4. CRM records and contacts. CRM ids also follow creation order.
    in_crm = sorted(
        (p for p in [*online, *leads] if p.crm_created is not None),
        key=lambda person: person.crm_created,
    )
    crm_customers: list[CrmCustomer] = []
    contacts: list[CrmContact] = []
    for number, person in enumerate(in_crm, start=1):
        person.crm_id = f"CRM-{number:07d}"
        created = person.crm_created
        updated = random_between(rng, created, cfg.window_end) if rng.random() < 0.25 else created
        crm_customers.append(
            CrmCustomer(
                crm_customer_id=person.crm_id,
                full_name=f"{person.first_name} {person.last_name}",
                segment=rng.choices(CRM_SEGMENTS, CRM_SEGMENT_WEIGHTS)[0],
                status="active" if rng.random() < 0.92 else "inactive",
                is_deleted=False,
                created_at=as_local_naive(created),
                updated_at=as_local_naive(updated),
            )
        )
        contacts.extend(_crm_contacts(rng, cfg, emails, person, len(contacts) + 1))

    # 5. E-commerce accounts, linked to the CRM by reference when a CRM record exists.
    ecommerce: list[Customer] = []
    for customer_id, person in enumerate(online, start=1):
        updated = person.signup
        if person.crm_created is not None and person.crm_created > person.signup:
            # The CRM reference was filled in later, when the CRM record appeared.
            filled = person.crm_created + timedelta(minutes=rng.randint(5, 600))
            updated = min(filled, last_moment)
        ecommerce.append(
            Customer(
                customer_id=customer_id,
                email=person.email,
                first_name=person.first_name,
                last_name=person.last_name,
                phone=person.phone,
                crm_customer_ref=person.crm_id,
                created_at=as_utc(person.signup),
                updated_at=as_utc(updated),
            )
        )

    return CustomerData(crm_customers, contacts, ecommerce)


def _signup_moment(
    rng: random.Random, cfg: GeneratorConfig, pre_history_start: datetime
) -> datetime:
    """30% of accounts predate the history; the rest grow over time (more recent signups)."""
    if rng.random() < 0.30:
        return random_between(rng, pre_history_start, cfg.window_start)
    start = as_utc(cfg.window_start)
    span = (as_utc(cfg.window_end) - start).total_seconds()
    return start + timedelta(seconds=int(span * rng.random() ** 0.75))


def _crm_contacts(
    rng: random.Random,
    cfg: GeneratorConfig,
    emails: EmailFactory,
    person: _Person,
    first_contact_id: int,
) -> list[CrmContact]:
    """One primary email; often a primary phone; sometimes extra, non-primary contacts."""
    created = person.crm_created
    entries: list[tuple[str, str, bool, datetime]] = [("email", person.email, True, created)]
    if rng.random() < 0.60:
        # Usually the same phone as the online account, sometimes a different one
        same_phone = person.signup is None or rng.random() < 0.80
        phone = person.phone if same_phone else random_phone(rng)
        entries.append(("phone", phone, True, created))
    if rng.random() < 0.10:
        extra_email = emails.new(person.first_name, person.last_name)
        entries.append(("email", extra_email, False, random_between(rng, created, cfg.window_end)))
    if rng.random() < 0.05:
        entries.append(
            ("phone", random_phone(rng), False, random_between(rng, created, cfg.window_end))
        )

    return [
        CrmContact(
            contact_id=first_contact_id + i,
            crm_customer_id=person.crm_id,
            contact_type=contact_type,
            contact_value=value,
            is_primary=is_primary,
            created_at=as_local_naive(moment),
            updated_at=as_local_naive(moment),
        )
        for i, (contact_type, value, is_primary, moment) in enumerate(entries)
    ]


def random_phone(rng: random.Random) -> str:
    """US phone in one canonical format, on the fictional 555 exchange."""
    area = rng.randint(201, 989)
    if area % 100 == 11:  # N11 codes are service numbers, not area codes
        area += 1
    return f"({area}) 555-{rng.randrange(10_000):04d}"


class EmailFactory:
    """Unique lowercase emails on reserved example domains."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self._used: set[str] = set()

    def new(self, first_name: str, last_name: str) -> str:
        first, last = _letters(first_name), _letters(last_name)
        local = self._rng.choice((f"{first}.{last}", f"{first}{last}", f"{first[0]}{last}"))
        if self._rng.random() < 0.5:
            local = f"{local}{self._rng.randint(1, 99)}"
        domain = self._rng.choice(EMAIL_DOMAINS)
        email = f"{local}@{domain}"
        while email in self._used:
            email = f"{local}{self._rng.randint(100, 99_999)}@{domain}"
        self._used.add(email)
        return email


def _letters(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower()) or "user"
