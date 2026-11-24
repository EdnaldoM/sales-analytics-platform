"""Planned data quality issues (docs/architecture/source-systems.md, section 6).

The other modules generate CLEAN data. This module damages it on purpose, in a
separate step, so that each issue is explicit, measurable and has a known rate.
Every issue maps to a technique the transformation layer must demonstrate.

| ID  | Injected here                                   | Rate          |
|-----|-------------------------------------------------|---------------|
| Q1  | email case and whitespace                       | ~15%          |
| Q2  | missing crm_customer_ref                        | 30% in total  |
| Q3  | same person twice in the CRM                    | ~2%           |
| Q4  | phone numbers in many formats                   | ~40%          |
| Q5  | SKU format variations                           | ~3%           |
| Q6  | SKU not found in the ERP                        | ~0.1%         |
| Q7  | duplicate payment rows (webhook retries)        | ~0.5%         |
| Q10 | missing phone, ship_postal_code, brand          | 2-10%         |
| Q11 | soft-deleted CRM records                        | ~1%           |
| Q12 | malformed shipping state                        | ~1%           |

Q8 (time zones) and Q9 (late updates) are not injected: they are built into
the way the data is generated.

The issues use their own random stream ("quality"), so changing a rate here
never changes which orders or customers exist.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta

from data_generator.catalog import CRM_SEGMENT_WEIGHTS, CRM_SEGMENTS, US_STATES
from data_generator.config import LOCAL_TZ, GeneratorConfig
from data_generator.orders import OrderBatch
from data_generator.records import CrmContact, CrmCustomer, Payment
from data_generator.reference import CustomerData, ErpData
from data_generator.timeutils import as_local_naive, random_between

EMAIL_VARIANT_SHARE = 0.15  # Q1
CRM_REF_MISSING_TARGET = 0.30  # Q2: total share, including customers not in the CRM
CRM_DUPLICATE_SHARE = 0.02  # Q3
PHONE_FORMAT_SHARE = 0.40  # Q4
SKU_VARIANT_SHARE = 0.03  # Q5
ORPHAN_SKU_SHARE = 0.001  # Q6
ORPHAN_SKU_COUNT = 25  # a small set of retired SKUs, so each one repeats
DUPLICATE_PAYMENT_SHARE = 0.005  # Q7
MISSING_PHONE_SHARE = 0.08  # Q10
MISSING_POSTAL_CODE_SHARE = 0.03  # Q10
MISSING_BRAND_SHARE = 0.05  # Q10
SOFT_DELETE_SHARE = 0.01  # Q11
BAD_STATE_SHARE = 0.01  # Q12

BAD_STATE_KINDS = ("name", "lower_name", "title_code", "lower_code", "invalid")
BAD_STATE_WEIGHTS = (35, 25, 15, 15, 10)
INVALID_STATES = ("XX", "N/A", "Unknown", "--")


class QualityInjector:
    """Applies the planned issues and counts how many rows each one touched.

    Usage:
        injector = QualityInjector(cfg)
        injector.apply_to_reference(erp, customers)
        for batch in batches:
            injector.apply_to_batch(batch)
        injector.counts   # rows touched per issue
    """

    def __init__(self, cfg: GeneratorConfig) -> None:
        self.cfg = cfg
        self.rng = cfg.rng("quality")
        self.counts: Counter[str] = Counter()
        self._state_names = {s.code: s.name for s in US_STATES}
        self._orphan_skus = [
            f"CK-{9000 + n}" for n in self.rng.sample(range(1000), ORPHAN_SKU_COUNT)
        ]
        self._next_payment_id = 1

    # -- reference data ------------------------------------------------------

    def apply_to_reference(self, erp: ErpData, customers: CustomerData) -> None:
        """ERP, CRM and e-commerce accounts. Order matters: duplicates (Q3)
        are created first, so that the formatting issues also reach them."""
        rng = self.rng

        for product in erp.products:  # Q10
            if rng.random() < MISSING_BRAND_SHARE:
                product.brand = None
                self.counts["Q10 products.brand null"] += 1

        self._duplicate_crm_customers(customers)  # Q3
        self._soft_delete_crm_customers(customers)  # Q11
        self._drop_crm_refs(customers)  # Q2

        for contact in customers.crm_contacts:
            if contact.contact_type == "email" and rng.random() < EMAIL_VARIANT_SHARE:
                contact.contact_value = self._email_variant(contact.contact_value)
                self.counts["Q1 crm email variant"] += 1
            elif contact.contact_type == "phone" and rng.random() < PHONE_FORMAT_SHARE:
                contact.contact_value = self._phone_variant(contact.contact_value)
                self.counts["Q4 crm phone format"] += 1

        for customer in customers.ecommerce_customers:
            if rng.random() < EMAIL_VARIANT_SHARE:
                customer.email = self._email_variant(customer.email)
                self.counts["Q1 ecommerce email variant"] += 1
            if rng.random() < MISSING_PHONE_SHARE:
                customer.phone = None
                self.counts["Q10 customers.phone null"] += 1
            elif rng.random() < PHONE_FORMAT_SHARE:
                customer.phone = self._phone_variant(customer.phone)
                self.counts["Q4 ecommerce phone format"] += 1

    def _duplicate_crm_customers(self, customers: CustomerData) -> None:
        """Q3: some people are registered again later, with the same email.

        CRM ids follow creation order, so all ids are renumbered after the
        duplicates are added; contacts and e-commerce references follow.
        """
        rng = self.rng
        contacts_by_customer: dict[str, list[CrmContact]] = {}
        for contact in customers.crm_contacts:
            contacts_by_customer.setdefault(contact.crm_customer_id, []).append(contact)

        originals = customers.crm_customers
        sample_size = round(len(originals) * CRM_DUPLICATE_SHARE)
        for original in rng.sample(originals, sample_size):
            created = random_between(rng, _local(original.created_at), self.cfg.window_end)
            duplicate_id = f"DUP-{original.crm_customer_id}"  # temporary, renumbered below
            customers.crm_customers.append(
                CrmCustomer(
                    crm_customer_id=duplicate_id,
                    full_name=rng.choice((str.strip, str.upper, str.lower))(original.full_name),
                    segment=rng.choices(CRM_SEGMENTS, CRM_SEGMENT_WEIGHTS)[0],
                    status="active",
                    is_deleted=False,
                    created_at=as_local_naive(created),
                    updated_at=as_local_naive(created),
                )
            )
            # The new record gets the person's primary contacts again
            for contact in contacts_by_customer[original.crm_customer_id]:
                if contact.is_primary:
                    customers.crm_contacts.append(
                        replace(
                            contact,
                            contact_id=len(customers.crm_contacts) + 1,
                            crm_customer_id=duplicate_id,
                            created_at=as_local_naive(created),
                            updated_at=as_local_naive(created),
                        )
                    )
        self.counts["Q3 crm duplicate"] += sample_size

        customers.crm_customers.sort(key=lambda c: c.created_at)  # stable: ties keep order
        new_ids = {
            c.crm_customer_id: f"CRM-{number:07d}"
            for number, c in enumerate(customers.crm_customers, start=1)
        }
        for crm_customer in customers.crm_customers:
            crm_customer.crm_customer_id = new_ids[crm_customer.crm_customer_id]
        for contact in customers.crm_contacts:
            contact.crm_customer_id = new_ids[contact.crm_customer_id]
        for customer in customers.ecommerce_customers:
            if customer.crm_customer_ref is not None:
                customer.crm_customer_ref = new_ids[customer.crm_customer_ref]

    def _soft_delete_crm_customers(self, customers: CustomerData) -> None:
        """Q11: deleting a record is an update (is_deleted), never a DELETE."""
        for crm_customer in customers.crm_customers:
            if self.rng.random() < SOFT_DELETE_SHARE:
                deleted = random_between(
                    self.rng, _local(crm_customer.updated_at), self.cfg.window_end
                )
                crm_customer.is_deleted = True
                crm_customer.updated_at = as_local_naive(deleted)
                self.counts["Q11 crm soft delete"] += 1

    def _drop_crm_refs(self, customers: CustomerData) -> None:
        """Q2: the reference is missing for 30% of accounts in total."""
        accounts = customers.ecommerce_customers
        linked = [c for c in accounts if c.crm_customer_ref is not None]
        missing_now = len(accounts) - len(linked)
        to_drop = max(round(len(accounts) * CRM_REF_MISSING_TARGET) - missing_now, 0)
        for customer in self.rng.sample(linked, to_drop):
            customer.crm_customer_ref = None
        self.counts["Q2 crm ref dropped"] += to_drop

    # -- transactions --------------------------------------------------------

    def apply_to_batch(self, batch: OrderBatch) -> None:
        """One month of orders. Call it for every batch, in order: payment ids
        are renumbered across batches to make room for duplicates (Q7)."""
        rng = self.rng

        for order in batch.orders:
            if rng.random() < MISSING_POSTAL_CODE_SHARE:  # Q10
                order.ship_postal_code = None
                self.counts["Q10 orders.ship_postal_code null"] += 1
            if rng.random() < BAD_STATE_SHARE:  # Q12
                order.ship_state = self._state_variant(order.ship_state)
                self.counts["Q12 bad ship_state"] += 1

        for item in batch.order_items:
            roll = rng.random()
            if roll < ORPHAN_SKU_SHARE:  # Q6
                item.sku = rng.choice(self._orphan_skus)
                self.counts["Q6 orphan sku"] += 1
            elif roll < ORPHAN_SKU_SHARE + SKU_VARIANT_SHARE:  # Q5
                item.sku = self._sku_variant(item.sku)
                self.counts["Q5 sku variant"] += 1

        payments: list[Payment] = []
        for payment in batch.payments:
            payment.payment_id = self._take_payment_id()
            payments.append(payment)
            if rng.random() < DUPLICATE_PAYMENT_SHARE:  # Q7
                received = payment.created_at + timedelta(seconds=rng.randint(1, 120))
                if received < self.cfg.window_end:
                    payments.append(
                        replace(
                            payment,
                            payment_id=self._take_payment_id(),
                            created_at=received,
                            updated_at=max(payment.updated_at, received),
                        )
                    )
                    self.counts["Q7 duplicate payment"] += 1
        batch.payments = payments

    def _take_payment_id(self) -> int:
        payment_id = self._next_payment_id
        self._next_payment_id += 1
        return payment_id

    # -- value variants ------------------------------------------------------

    def _email_variant(self, email: str) -> str:
        """Q1: `john.doe@example.com` -> `John.Doe@Example.com `, `JOHN.DOE@...`."""
        kind = self.rng.randrange(4)
        if kind == 0:
            local, domain = email.split("@")
            return f"{'.'.join(p.capitalize() for p in local.split('.'))}@{domain.capitalize()}"
        if kind == 1:
            return email.upper()
        if kind == 2:
            return f"{email} "
        return f" {email.capitalize()}"

    def _phone_variant(self, phone: str) -> str:
        """Q4: `(212) 555-0100` -> `212.555.0100`, `+1 212 555 0100`, ..."""
        digits = "".join(ch for ch in phone if ch.isdigit())
        area, exchange, line = digits[:3], digits[3:6], digits[6:]
        return self.rng.choice(
            (
                f"{area}.{exchange}.{line}",
                f"{area}-{exchange}-{line}",
                f"+1 {area} {exchange} {line}",
                f"+1{digits}",
                digits,
                f"1-{area}-{exchange}-{line}",
            )
        )

    def _sku_variant(self, sku: str) -> str:
        """Q5: `CK-1001` -> `ck-1001`, ` CK-1001`, `CK1001`, `CK-1001 `."""
        return self.rng.choice((sku.lower(), f" {sku}", sku.replace("-", ""), f"{sku} "))

    def _state_variant(self, code: str) -> str:
        """Q12: `CA` -> `California`, `california`, `Ca`, `ca` or an invalid value."""
        kind = self.rng.choices(BAD_STATE_KINDS, BAD_STATE_WEIGHTS)[0]
        name = self._state_names[code]
        if kind == "name":
            return name
        if kind == "lower_name":
            return name.lower()
        if kind == "title_code":
            return code.capitalize()
        if kind == "lower_code":
            return code.lower()
        return self.rng.choice(INVALID_STATES)


def _local(naive: datetime) -> datetime:
    """CRM timestamp (local wall-clock time) back to an aware moment."""
    return naive.replace(tzinfo=LOCAL_TZ)
