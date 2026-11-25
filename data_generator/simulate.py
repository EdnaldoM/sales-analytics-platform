"""Incremental source activity: each run adds "a little more life" to the sources.

`make seed` builds the history up to the anchor date. `make simulate` then acts
like the operational systems working normally, with REAL timestamps (now()):

| System     | One run                                                          |
|------------|------------------------------------------------------------------|
| ERP        | a few list price changes, a discontinued product, cost revisions |
| CRM        | new customers and contacts, segment and status changes, soft     |
|            | deletes                                                          |
| E-commerce | new accounts and profile updates, ~400 new orders (~1,000        |
|            | items), open orders moving forward, new returns and refunds      |

Every run is one "tick" of time: each open order or return has a chance to
move to its next status. Old orders that were still open at the anchor date
are updated days or weeks after they were created (Q9: late-arriving data).

New rows get the same planned issues as the history (Q1, Q4-Q7, Q10, Q12).
Inserts leave created_at/updated_at to the database defaults, and updates go
through the updated_at triggers, so the incremental cursor (updated_at) of the
ingestion layer sees every change.

Unlike the seed, runs are not reproducible: they depend on the current data
and on the clock. --seed only fixes the random choices.
"""

from __future__ import annotations

import logging
import random
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import psycopg
from faker import Faker

from data_generator import db
from data_generator.catalog import CRM_SEGMENTS, US_STATES
from data_generator.config import LOCAL_TZ
from data_generator.orders import (
    FREE_SHIPPING_THRESHOLD,
    GUEST_SHARE,
    ITEM_DISCOUNT_RATES,
    ITEM_DISCOUNT_SHARE,
    ITEMS_PER_ORDER,
    ITEMS_PER_ORDER_WEIGHTS,
    PAYMENT_METHOD_WEIGHTS,
    PAYMENT_METHODS,
    QUANTITIES,
    QUANTITY_WEIGHTS,
    RETURN_REASON_WEIGHTS,
    RETURN_REASONS,
    SHIPPING_FEE,
    ZERO,
    allocate_coupon,
    campaign,
    money,
)
from data_generator.quality import (
    BAD_STATE_SHARE,
    DUPLICATE_PAYMENT_SHARE,
    EMAIL_VARIANT_SHARE,
    MISSING_PHONE_SHARE,
    MISSING_POSTAL_CODE_SHARE,
    ORPHAN_SKU_SHARE,
    PHONE_FORMAT_SHARE,
    SKU_VARIANT_SHARE,
    email_variant,
    phone_variant,
    sku_variant,
    state_variant,
)
from data_generator.reference import EmailFactory, random_phone

log = logging.getLogger(__name__)

# -- Volumes per run (docs/architecture/source-systems.md, section 7) ---------
ORDERS_PER_RUN = 400
NEW_ACCOUNTS_PER_RUN = 50
PROFILE_UPDATES_PER_RUN = 20
NEW_RETURNS_PER_RUN = 25
NEW_CRM_CUSTOMERS_PER_RUN = 50
CRM_FROM_ONLINE_SHARE = 0.6  # new CRM records for online customers who had none
CRM_REF_FILLED_SHARE = 0.7  # ...and the e-commerce account gets the reference (Q2 otherwise)
EXTRA_CONTACTS_PER_RUN = 15
SEGMENT_CHANGES_PER_RUN = 100  # drives the customer history (SCD2)
CRM_STATUS_CHANGES_PER_RUN = 10
SOFT_DELETES_PER_RUN = 3  # Q11
PRICE_CHANGES_PER_RUN = 5
DISCONTINUED_PER_RUN = 1
COST_REVISIONS_PER_RUN = 5

# -- One tick of time: chance that an open record moves on --------------------
# order status: (next status, chance), checked in order; otherwise it stays
ORDER_TRANSITIONS = {
    "pending_payment": (("paid", 0.90), ("cancelled", 0.05)),  # payment captured / failed
    "paid": (("shipped", 0.60), ("cancelled", 0.02)),
    "shipped": (("delivered", 0.50),),
}
# A pending order whose payment attempts all failed can only be cancelled
PENDING_WITHOUT_PAYMENT = (("cancelled", 0.50),)
RETURN_TRANSITIONS = {
    "requested": (("approved", 0.60), ("rejected", 0.05)),
    "approved": (("received", 0.50),),
    "received": (("refunded", 0.60),),
}
RECENT_DELIVERY_DAYS = 30  # returns are requested for recently delivered orders
REGULAR_BUYER_SHARE = 0.85  # orders from customers who bought in the last year
ITEM_IN_RETURN_SHARE = 0.6


@dataclass(frozen=True)
class _Product:
    sku: str
    list_price: Decimal
    weight: float  # cheaper items sell more often


def run(seed: int | None = None, orders: int = ORDERS_PER_RUN) -> Counter[str]:
    """One run of activity in the three systems. Returns what changed."""
    rng = random.Random(seed)
    fake = Faker("en_US")
    fake.seed_instance(rng.getrandbits(64))
    changes: Counter[str] = Counter()

    # Each system is its own transaction, as in independent real systems.
    with db.connect("erp") as erp:
        _erp_activity(erp, rng, changes)
        products = _active_products(erp)

    with db.connect("ecommerce") as ecommerce, db.connect("crm") as crm:
        new_refs = _crm_activity(crm, ecommerce, rng, fake, changes)
        crm.commit()
        _ecommerce_activity(ecommerce, rng, fake, products, new_refs, orders, changes)

    for change, count in sorted(changes.items()):
        log.info("%-48s %s", change, f"{count:,}")
    return changes


# ==========================================================================
# ERP
# ==========================================================================


def _erp_activity(conn: psycopg.Connection, rng: random.Random, changes: Counter[str]) -> None:
    for product_id, price in conn.execute(
        "SELECT product_id, list_price FROM products WHERE is_active ORDER BY random() LIMIT %s",
        (PRICE_CHANGES_PER_RUN,),
    ).fetchall():
        new_price = max(int(float(price) * rng.uniform(0.90, 1.12)), 1) + Decimal("0.99")
        conn.execute(
            "UPDATE products SET list_price = %s WHERE product_id = %s", (new_price, product_id)
        )
        changes["erp.products price changed"] += 1

    discontinued = conn.execute(
        "UPDATE products SET is_active = false WHERE product_id IN "
        "(SELECT product_id FROM products WHERE is_active ORDER BY random() LIMIT %s)",
        (DISCONTINUED_PER_RUN,),
    ).rowcount
    changes["erp.products discontinued"] += discontinued

    # A cost revision closes the open period today and opens a new one (business date).
    today = "(now() AT TIME ZONE 'America/New_York')::date"
    for cost_id, product_id, unit_cost in conn.execute(
        "SELECT cost_id, product_id, unit_cost FROM product_cost_history "
        f"WHERE valid_to IS NULL AND valid_from < {today} ORDER BY random() LIMIT %s",
        (COST_REVISIONS_PER_RUN,),
    ).fetchall():
        conn.execute(
            f"UPDATE product_cost_history SET valid_to = {today} WHERE cost_id = %s", (cost_id,)
        )
        conn.execute(
            "INSERT INTO product_cost_history (product_id, unit_cost, valid_from) "
            f"VALUES (%s, %s, {today})",
            (product_id, money(unit_cost * Decimal(str(rng.uniform(0.97, 1.10))))),
        )
        changes["erp.product_cost_history revised"] += 1


def _active_products(conn: psycopg.Connection) -> list[_Product]:
    rows = conn.execute("SELECT sku, list_price FROM products WHERE is_active").fetchall()
    return [_Product(sku, price, float(price) ** -0.35) for sku, price in rows]


# ==========================================================================
# CRM
# ==========================================================================


def _crm_activity(
    crm: psycopg.Connection,
    ecommerce: psycopg.Connection,
    rng: random.Random,
    fake: Faker,
    changes: Counter[str],
) -> dict[int, str]:
    """CRM changes. Returns {e-commerce customer_id: new crm_customer_id} to link."""
    last_number = crm.execute(
        "SELECT COALESCE(MAX(substring(crm_customer_id FROM 5)::int), 0) FROM customers"
    ).fetchone()[0]
    known_emails = {
        row[0]
        for row in crm.execute(
            "SELECT lower(btrim(contact_value)) FROM customer_contacts WHERE contact_type = 'email'"
        )
    }

    # People to register: recent online customers without a CRM record, and new leads
    from_online = round(NEW_CRM_CUSTOMERS_PER_RUN * CRM_FROM_ONLINE_SHARE)
    candidates = ecommerce.execute(
        "SELECT customer_id, first_name, last_name, lower(btrim(email)), phone FROM customers "
        "WHERE crm_customer_ref IS NULL ORDER BY created_at DESC LIMIT %s",
        (from_online * 5,),
    ).fetchall()
    people = [c for c in candidates if c[3] not in known_emails][:from_online]
    emails = EmailFactory(rng)
    for _ in range(NEW_CRM_CUSTOMERS_PER_RUN - len(people)):
        first, last = fake.first_name(), fake.last_name()
        people.append((None, first, last, emails.new(first, last), random_phone(rng)))

    links: dict[int, str] = {}
    for offset, (customer_id, first, last, email, phone) in enumerate(people, start=1):
        crm_id = f"CRM-{last_number + offset:07d}"
        crm.execute(
            "INSERT INTO customers (crm_customer_id, full_name, segment, status) "
            "VALUES (%s, %s, 'bronze', 'active')",
            (crm_id, f"{first} {last}"),
        )
        _insert_contact(crm, rng, crm_id, "email", email, True)
        if rng.random() < 0.6:
            _insert_contact(crm, rng, crm_id, "phone", phone or random_phone(rng), True)
        if customer_id is not None and rng.random() < CRM_REF_FILLED_SHARE:
            links[customer_id] = crm_id
    changes["crm.customers new"] += len(people)

    for (crm_id,) in crm.execute(
        "SELECT crm_customer_id FROM customers WHERE NOT is_deleted ORDER BY random() LIMIT %s",
        (EXTRA_CONTACTS_PER_RUN,),
    ).fetchall():
        _insert_contact(crm, rng, crm_id, "phone", random_phone(rng), False)
    changes["crm.customer_contacts extra"] += EXTRA_CONTACTS_PER_RUN

    # Segment changes move one level up or down (bronze <-> silver <-> gold <-> platinum)
    for crm_id, segment in crm.execute(
        "SELECT crm_customer_id, segment FROM customers WHERE NOT is_deleted "
        "ORDER BY random() LIMIT %s",
        (SEGMENT_CHANGES_PER_RUN,),
    ).fetchall():
        level = CRM_SEGMENTS.index(segment)
        step = (
            rng.choice((-1, 1)) if 0 < level < len(CRM_SEGMENTS) - 1 else (1 if level == 0 else -1)
        )
        crm.execute(
            "UPDATE customers SET segment = %s WHERE crm_customer_id = %s",
            (CRM_SEGMENTS[level + step], crm_id),
        )
    changes["crm.customers segment changed"] += SEGMENT_CHANGES_PER_RUN

    changes["crm.customers status changed"] += crm.execute(
        "UPDATE customers SET status = CASE status WHEN 'active' THEN 'inactive' ELSE 'active' END "
        "WHERE crm_customer_id IN (SELECT crm_customer_id FROM customers WHERE NOT is_deleted "
        "ORDER BY random() LIMIT %s)",
        (CRM_STATUS_CHANGES_PER_RUN,),
    ).rowcount
    changes["crm.customers soft deleted (Q11)"] += crm.execute(
        "UPDATE customers SET is_deleted = true WHERE crm_customer_id IN "
        "(SELECT crm_customer_id FROM customers WHERE NOT is_deleted ORDER BY random() LIMIT %s)",
        (SOFT_DELETES_PER_RUN,),
    ).rowcount
    return links


def _insert_contact(
    crm: psycopg.Connection,
    rng: random.Random,
    crm_id: str,
    contact_type: str,
    value: str,
    is_primary: bool,
) -> None:
    if contact_type == "email" and rng.random() < EMAIL_VARIANT_SHARE:
        value = email_variant(rng, value)  # Q1
    if contact_type == "phone" and rng.random() < PHONE_FORMAT_SHARE:
        value = phone_variant(rng, value)  # Q4
    crm.execute(
        "INSERT INTO customer_contacts (crm_customer_id, contact_type, contact_value, is_primary) "
        "VALUES (%s, %s, %s, %s)",
        (crm_id, contact_type, value, is_primary),
    )


# ==========================================================================
# E-commerce
# ==========================================================================


def _ecommerce_activity(
    conn: psycopg.Connection,
    rng: random.Random,
    fake: Faker,
    products: list[_Product],
    new_refs: dict[int, str],
    order_count: int,
    changes: Counter[str],
) -> None:
    # Existing data moves first, so that this run's new orders start as pending.
    _advance_orders(conn, rng, changes)
    _advance_returns(conn, rng, changes)
    _new_returns(conn, rng, changes)

    for customer_id, crm_id in new_refs.items():
        conn.execute(
            "UPDATE customers SET crm_customer_ref = %s WHERE customer_id = %s",
            (crm_id, customer_id),
        )
    changes["ecommerce.customers crm ref filled"] += len(new_refs)

    _new_accounts(conn, rng, fake, changes)
    for (customer_id,) in conn.execute(
        "SELECT customer_id FROM customers ORDER BY random() LIMIT %s",
        (PROFILE_UPDATES_PER_RUN,),
    ).fetchall():
        conn.execute(
            "UPDATE customers SET phone = %s WHERE customer_id = %s",
            (random_phone(rng), customer_id),
        )
    changes["ecommerce.customers phone changed"] += PROFILE_UPDATES_PER_RUN

    _new_orders(conn, rng, fake, products, order_count, changes)


def _advance_orders(conn: psycopg.Connection, rng: random.Random, changes: Counter[str]) -> None:
    # Cancelled orders whose captured payment was not refunded yet (cancelled near the anchor)
    pending_refunds = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT order_id FROM payments p JOIN orders o USING (order_id) "
            "WHERE o.order_status = 'cancelled' AND p.payment_status = 'captured'"
        )
        if rng.random() < 0.5
    ]
    changes["ecommerce.payments refunded (cancelled order)"] += conn.execute(
        "UPDATE payments SET payment_status = 'refunded' "
        "WHERE order_id = ANY(%s) AND payment_status = 'captured'",
        (pending_refunds,),
    ).rowcount

    moves: dict[tuple[str, str], list[int]] = {}
    for order_id, status, authorized in conn.execute(
        "SELECT order_id, order_status, EXISTS (SELECT 1 FROM payments p "
        "WHERE p.order_id = o.order_id AND p.payment_status = 'authorized') "
        "FROM orders o WHERE order_status = ANY(%s)",
        (list(ORDER_TRANSITIONS),),
    ).fetchall():
        transitions = ORDER_TRANSITIONS[status]
        if status == "pending_payment" and not authorized:
            transitions = PENDING_WITHOUT_PAYMENT
        target = _next_status(rng, transitions)
        if target is not None:
            moves.setdefault((status, target), []).append(order_id)

    for (status, target), ids in moves.items():
        if target == "cancelled":
            conn.execute(
                "UPDATE orders SET order_status = 'cancelled', cancelled_at = now() "
                "WHERE order_id = ANY(%s)",
                (ids,),
            )
        else:
            conn.execute(
                "UPDATE orders SET order_status = %s WHERE order_id = ANY(%s)", (target, ids)
            )
        # Payment side: capture, failure, or refund of a captured payment
        payment_change = {
            ("pending_payment", "paid"): ("authorized", "captured"),
            ("pending_payment", "cancelled"): ("authorized", "failed"),
            ("paid", "cancelled"): ("captured", "refunded"),
        }.get((status, target))
        if payment_change is not None:
            conn.execute(
                "UPDATE payments SET payment_status = %s "
                "WHERE order_id = ANY(%s) AND payment_status = %s",
                (payment_change[1], ids, payment_change[0]),
            )
        changes[f"ecommerce.orders {status} -> {target}"] += len(ids)


def _advance_returns(conn: psycopg.Connection, rng: random.Random, changes: Counter[str]) -> None:
    for return_id, status in conn.execute(
        "SELECT return_id, return_status FROM returns WHERE return_status = ANY(%s)",
        (list(RETURN_TRANSITIONS),),
    ).fetchall():
        target = _next_status(rng, RETURN_TRANSITIONS[status])
        if target is None:
            continue
        conn.execute(
            "UPDATE returns SET return_status = %s, "
            "refunded_at = CASE WHEN %s::text = 'refunded' THEN now() ELSE refunded_at END "
            "WHERE return_id = %s",
            (target, target, return_id),
        )
        changes[f"ecommerce.returns {status} -> {target}"] += 1


def _new_returns(conn: psycopg.Connection, rng: random.Random, changes: Counter[str]) -> None:
    """Returns for recently delivered orders that have none yet."""
    orders = conn.execute(
        "SELECT order_id, order_discount_amount FROM orders o "
        "WHERE order_status = 'delivered' AND updated_at >= now() - make_interval(days => %s) "
        "AND NOT EXISTS (SELECT 1 FROM returns r WHERE r.order_id = o.order_id) "
        "ORDER BY random() LIMIT %s",
        (RECENT_DELIVERY_DAYS, NEW_RETURNS_PER_RUN),
    ).fetchall()
    for order_id, order_discount in orders:
        items = conn.execute(
            "SELECT order_item_id, quantity, unit_price * quantity - item_discount_amount "
            "FROM order_items WHERE order_id = %s ORDER BY line_number",
            (order_id,),
        ).fetchall()
        # Net value per line: same coupon allocation as the order (metrics-definition.md)
        nets = [
            base - allocated
            for (_, _, base), allocated in zip(
                items, allocate_coupon(order_discount, [i[2] for i in items]), strict=True
            )
        ]
        chosen = [i for i in range(len(items)) if rng.random() < ITEM_IN_RETURN_SHARE]
        chosen = chosen or [rng.randrange(len(items))]

        return_id = conn.execute(
            "INSERT INTO returns (order_id, return_status, reason_code, requested_at) "
            "VALUES (%s, 'requested', %s, now()) RETURNING return_id",
            (order_id, rng.choices(RETURN_REASONS, RETURN_REASON_WEIGHTS)[0]),
        ).fetchone()[0]
        for i in chosen:
            order_item_id, quantity, _ = items[i]
            returned = rng.randint(1, quantity)
            conn.execute(
                "INSERT INTO return_items "
                "(return_id, order_item_id, quantity_returned, refund_amount) "
                "VALUES (%s, %s, %s, %s)",
                (return_id, order_item_id, returned, money(nets[i] / quantity * returned)),
            )
            changes["ecommerce.return_items new"] += 1
        changes["ecommerce.returns new"] += 1


def _new_accounts(
    conn: psycopg.Connection, rng: random.Random, fake: Faker, changes: Counter[str]
) -> None:
    emails = EmailFactory(rng)
    for _ in range(NEW_ACCOUNTS_PER_RUN):
        first, last = fake.first_name(), fake.last_name()
        phone: str | None = random_phone(rng)
        if rng.random() < MISSING_PHONE_SHARE:
            phone = None  # Q10
        elif rng.random() < PHONE_FORMAT_SHARE:
            phone = phone_variant(rng, phone)  # Q4
        # Login emails are unique: on a clash with an existing account, try another one
        for _attempt in range(5):
            email = emails.new(first, last)
            if rng.random() < EMAIL_VARIANT_SHARE:
                email = email_variant(rng, email)  # Q1
            inserted = conn.execute(
                "INSERT INTO customers (email, first_name, last_name, phone) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (email, first, last, phone),
            ).rowcount
            if inserted:
                changes["ecommerce.customers new"] += 1
                break


def _new_orders(
    conn: psycopg.Connection,
    rng: random.Random,
    fake: Faker,
    products: list[_Product],
    count: int,
    changes: Counter[str],
) -> None:
    """New orders start as pending_payment with an authorized payment."""
    # Picking a past order's customer favors frequent buyers (keeps the Pareto shape)
    regular = [
        row[0]
        for row in conn.execute(
            "SELECT customer_id FROM orders WHERE customer_id IS NOT NULL "
            "AND order_ts >= now() - interval '365 days'"
        )
    ]
    everyone = [row[0] for row in conn.execute("SELECT customer_id FROM customers")]
    order_ids = [
        row[0]
        for row in conn.execute(
            "SELECT nextval(pg_get_serial_sequence('orders', 'order_id')) "
            "FROM generate_series(1, %s)",
            (count,),
        )
    ]
    product_weights = [p.weight for p in products]
    states = [s.code for s in US_STATES]
    state_weights = [s.population_m for s in US_STATES]
    tax_rate = {s.code: Decimal(str(s.sales_tax_pct)) / 100 for s in US_STATES}
    emails = EmailFactory(rng)
    now = datetime.now(UTC)
    today = now.astimezone(LOCAL_TZ).date()

    for order_id in order_ids:
        guest_email = None
        customer_id = None
        if rng.random() < GUEST_SHARE:
            guest_email = emails.new(fake.first_name(), fake.last_name())
        elif regular and rng.random() < REGULAR_BUYER_SHARE:
            customer_id = rng.choice(regular)
        else:
            customer_id = rng.choice(everyone)

        lines = []
        size = rng.choices(ITEMS_PER_ORDER, ITEMS_PER_ORDER_WEIGHTS)[0]
        for product in rng.choices(products, product_weights, k=size):
            quantity = rng.choices(QUANTITIES, QUANTITY_WEIGHTS)[0]
            gross = product.list_price * quantity
            discount = ZERO
            if rng.random() < ITEM_DISCOUNT_SHARE:
                discount = money(gross * rng.choice(ITEM_DISCOUNT_RATES))
            lines.append((product, quantity, discount, gross - discount))

        state = rng.choices(states, state_weights)[0]
        bases = [line[3] for line in lines]
        coupon_code, order_discount = _coupon(rng, today, bases)
        nets = [b - a for b, a in zip(bases, allocate_coupon(order_discount, bases), strict=True)]
        taxes = [money(net * tax_rate[state]) for net in nets]
        shipping = ZERO if sum(nets, ZERO) >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE
        amount = sum(nets, ZERO) + sum(taxes, ZERO) + shipping

        postal_code = fake.zipcode_in_state(state)
        if rng.random() < MISSING_POSTAL_CODE_SHARE:
            postal_code = None  # Q10
        ship_state = state_variant(rng, state) if rng.random() < BAD_STATE_SHARE else state  # Q12
        ordered = now - timedelta(seconds=rng.randrange(3_600))  # since the previous hour
        conn.execute(
            "INSERT INTO orders (order_id, order_number, customer_id, guest_email, order_status, "
            "order_ts, coupon_code, order_discount_amount, shipping_amount, ship_city, "
            "ship_state, ship_postal_code) "
            "VALUES (%s, %s, %s, %s, 'pending_payment', %s, %s, %s, %s, %s, %s, %s)",
            (
                order_id,
                f"ORD-{today.year}-{order_id:07d}",
                customer_id,
                guest_email,
                ordered,
                coupon_code,
                order_discount,
                shipping,
                fake.city(),
                ship_state,
                postal_code,
            ),
        )

        items = []
        for line_number, ((product, quantity, discount, _), tax) in enumerate(
            zip(lines, taxes, strict=True), start=1
        ):
            items.append(
                (order_id, line_number, _sku(rng, product.sku), quantity, product.list_price,
                 discount, tax)
            )  # fmt: skip
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO order_items (order_id, line_number, sku, quantity, unit_price, "
                "item_discount_amount, tax_amount) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                items,
            )

        payment = (
            order_id,
            rng.choices(PAYMENT_METHODS, PAYMENT_METHOD_WEIGHTS)[0],
            amount,
            f"txn_{rng.getrandbits(64):016x}",
        )
        copies = 2 if rng.random() < DUPLICATE_PAYMENT_SHARE else 1  # Q7: webhook retry
        for _ in range(copies):
            conn.execute(
                "INSERT INTO payments (order_id, attempt_number, payment_method, payment_status, "
                "amount, provider_transaction_id) VALUES (%s, 1, %s, 'authorized', %s, %s)",
                payment,
            )
        changes["ecommerce.orders new"] += 1
        changes["ecommerce.order_items new"] += len(items)
        changes["ecommerce.payments new"] += copies


def _coupon(rng: random.Random, today: date, bases: list[Decimal]) -> tuple[str | None, Decimal]:
    active = campaign(today)
    if active is not None and rng.random() < active[2]:
        code, rate = active[0], active[1]
    elif rng.random() < 0.04:
        code, rate = "SAVE10", Decimal("0.10")
    else:
        return None, ZERO
    return code, money(sum(bases, ZERO) * rate)


def _sku(rng: random.Random, sku: str) -> str:
    roll = rng.random()
    if roll < ORPHAN_SKU_SHARE:
        return f"CK-{9000 + rng.randrange(1000)}"  # Q6: not in the ERP
    if roll < ORPHAN_SKU_SHARE + SKU_VARIANT_SHARE:
        return sku_variant(rng, sku)  # Q5
    return sku


def _next_status(rng: random.Random, transitions: tuple[tuple[str, float], ...]) -> str | None:
    roll = rng.random()
    for target, chance in transitions:
        if roll < chance:
            return target
        roll -= chance
    return None
