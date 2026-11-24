"""Rules that must always hold in the generated data.

Business rules are checked on the clean data. Structural rules (keys,
references, time window) are checked on the data with quality issues, because
the issues must not break what the source systems themselves enforce.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

from tests.conftest import Dataset

ZERO = Decimal("0.00")


# -- orders and payments ------------------------------------------------------


def test_payment_amount_matches_the_order_total(clean: Dataset) -> None:
    """amount = items net of discounts and coupon + tax + shipping."""
    due: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for item in clean.order_items:
        net = item.unit_price * item.quantity - item.item_discount_amount
        due[item.order_id] += net + item.tax_amount
    for order in clean.orders:
        due[order.order_id] += order.shipping_amount - order.order_discount_amount
    assert all(p.amount == due[p.order_id] for p in clean.payments)


def test_every_order_has_consecutive_lines(dataset: Dataset) -> None:
    lines: dict[int, list[int]] = defaultdict(list)
    for item in dataset.order_items:
        lines[item.order_id].append(item.line_number)
    assert set(lines) == {o.order_id for o in dataset.orders}
    assert all(numbers == list(range(1, len(numbers) + 1)) for numbers in lines.values())


def test_cancelled_at_is_set_only_on_cancelled_orders(dataset: Dataset) -> None:
    for order in dataset.orders:
        assert (order.cancelled_at is not None) == (order.order_status == "cancelled")


def test_guest_orders_have_an_email_instead_of_a_customer(dataset: Dataset) -> None:
    for order in dataset.orders:
        assert (order.customer_id is None) == (order.guest_email is not None)


# -- returns ------------------------------------------------------------------


def test_returns_only_for_delivered_orders(clean: Dataset) -> None:
    status = {o.order_id: o.order_status for o in clean.orders}
    assert clean.returns, "the small dataset should still have returns"
    assert all(status[r.order_id] == "delivered" for r in clean.returns)


def test_returned_quantity_never_exceeds_the_quantity_sold(clean: Dataset) -> None:
    sold = {i.order_item_id: i.quantity for i in clean.order_items}
    returned: Counter[int] = Counter()
    for item in clean.return_items:
        returned[item.order_item_id] += item.quantity_returned
    assert all(quantity <= sold[item_id] for item_id, quantity in returned.items())


def test_refunded_at_is_set_only_on_refunded_returns(clean: Dataset) -> None:
    for entry in clean.returns:
        assert (entry.refunded_at is not None) == (entry.return_status == "refunded")
        assert entry.refunded_at is None or entry.refunded_at >= entry.requested_at


# -- time ---------------------------------------------------------------------


def all_rows(data: Dataset) -> list:
    return [
        *data.erp.categories,
        *data.erp.products,
        *data.erp.costs,
        *data.customers.crm_customers,
        *data.customers.crm_contacts,
        *data.customers.ecommerce_customers,
        *data.orders,
        *data.order_items,
        *data.payments,
        *data.returns,
        *data.return_items,
    ]


def test_nothing_happens_after_the_anchor_date(dataset: Dataset) -> None:
    end_utc = dataset.cfg.window_end
    end_local = end_utc.replace(tzinfo=None)  # CRM/ERP store local time without a zone (Q8)
    for row in all_rows(dataset):
        end = end_local if row.updated_at.tzinfo is None else end_utc
        assert row.created_at <= row.updated_at < end, row


def test_time_zone_convention_per_system(dataset: Dataset) -> None:
    """E-commerce: aware UTC. CRM and ERP: local time without a zone (Q8)."""
    for customer in dataset.customers.ecommerce_customers:
        assert customer.created_at.utcoffset().total_seconds() == 0
    for crm_customer in dataset.customers.crm_customers:
        assert crm_customer.created_at.tzinfo is None
    for product in dataset.erp.products:
        assert product.created_at.tzinfo is None


# -- reference data -------------------------------------------------------------


def test_one_open_cost_row_per_product_and_no_overlaps(dataset: Dataset) -> None:
    periods = defaultdict(list)
    for cost in dataset.erp.costs:
        periods[cost.product_id].append(cost)
    assert set(periods) == {p.product_id for p in dataset.erp.products}
    for rows in periods.values():
        rows.sort(key=lambda c: c.valid_from)
        assert [c.valid_to is None for c in rows].count(True) == 1
        assert rows[-1].valid_to is None
        for previous, following in zip(rows, rows[1:], strict=False):
            assert previous.valid_to == following.valid_from


def test_crm_ids_follow_creation_order(dataset: Dataset) -> None:
    crm = dataset.customers.crm_customers
    assert [c.crm_customer_id for c in crm] == [f"CRM-{n:07d}" for n in range(1, len(crm) + 1)]
    created = [c.created_at for c in crm]
    assert created == sorted(created)


def test_references_point_to_existing_records(dataset: Dataset) -> None:
    crm_ids = {c.crm_customer_id for c in dataset.customers.crm_customers}
    assert all(c.crm_customer_id in crm_ids for c in dataset.customers.crm_contacts)
    refs = [c.crm_customer_ref for c in dataset.customers.ecommerce_customers]
    assert all(ref in crm_ids for ref in refs if ref is not None)


def test_at_most_one_primary_contact_per_type(dataset: Dataset) -> None:
    """Same rule as the partial unique index in the CRM database."""
    primaries = Counter(
        (c.crm_customer_id, c.contact_type) for c in dataset.customers.crm_contacts if c.is_primary
    )
    assert max(primaries.values()) == 1


def test_login_emails_are_unique_after_normalization(dataset: Dataset) -> None:
    """Q1 changes case and spaces, but the e-commerce unique index still holds."""
    emails = [c.email.strip().lower() for c in dataset.customers.ecommerce_customers]
    assert len(emails) == len(set(emails))


# -- planned quality issues -------------------------------------------------------


def test_q2_crm_reference_missing_for_30_percent(dataset: Dataset) -> None:
    accounts = dataset.customers.ecommerce_customers
    missing = sum(c.crm_customer_ref is None for c in accounts)
    assert missing == round(len(accounts) * 0.30)


def test_q7_duplicate_payments_keep_unique_ids(dataset: Dataset) -> None:
    ids = [p.payment_id for p in dataset.payments]
    assert ids == list(range(1, len(ids) + 1))
    by_transaction = Counter(p.provider_transaction_id for p in dataset.payments)
    assert max(by_transaction.values()) == 2  # webhook retries exist, never triplicated


def test_issues_appear_only_after_injection(clean: Dataset, dataset: Dataset) -> None:
    def malformed_skus(data: Dataset) -> int:
        return sum(not i.sku.startswith("CK-") or i.sku != i.sku.strip() for i in data.order_items)

    def malformed_states(data: Dataset) -> int:
        return sum(not (len(o.ship_state) == 2 and o.ship_state.isupper()) for o in data.orders)

    assert malformed_skus(clean) == 0 and malformed_skus(dataset) > 0
    assert malformed_states(clean) == 0 and malformed_states(dataset) > 0
