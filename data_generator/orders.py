"""Orders and their lifecycle: orders, order items, payments and returns.

Business patterns are built in on purpose, so that each analysis has something
to show:
- growth (~15% a year), seasonality (November/December peak, Black Friday)
  and more orders on weekends;
- a few customers buy a lot (Pareto), and 5% of orders are guest checkouts;
- prices drift over time; item discounts and coupon campaigns;
- each order follows its status lifecycle up to the anchor date: old orders
  are delivered (or cancelled), recent ones are still open;
- returns happen after delivery, at a different rate per category.

Money follows docs/business/metrics-definition.md: coupons are allocated to
items proportionally, and tax is computed on each item's net value.

Orders are produced month by month (a Python generator, `yield`), so memory
stays small even with ~1 million order items.
"""

from __future__ import annotations

import random
from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from itertools import accumulate

from faker import Faker

from data_generator.catalog import CATALOG, US_STATES, ParentCategory
from data_generator.config import LOCAL_TZ, GeneratorConfig
from data_generator.records import Order, OrderItem, Payment, Return, ReturnItem
from data_generator.reference import CustomerData, EmailFactory, ErpData
from data_generator.timeutils import as_utc

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

# -- Demand shape (when orders happen) --------------------------------------
ANNUAL_GROWTH = 0.15
WEEKEND_FACTOR = 1.15
MONTH_FACTORS = {
    1: 0.85, 2: 0.80, 3: 0.95, 4: 0.95, 5: 1.00, 6: 1.00,
    7: 0.95, 8: 1.00, 9: 0.95, 10: 1.05, 11: 1.35, 12: 1.60,
}  # fmt: skip
# Orders per local hour of the day: quiet at night, peak in the evening
HOUR_WEIGHTS = (
    1.0, 0.6, 0.4, 0.3, 0.3, 0.4, 0.8, 1.5, 2.2, 2.8, 3.0, 3.2,
    3.4, 3.2, 3.0, 3.0, 3.1, 3.3, 3.8, 4.2, 4.4, 4.0, 3.0, 1.8,
)  # fmt: skip
# Category demand by month (default 1.0)
SEASONAL_FACTORS: dict[str, dict[int, float]] = {
    "OUTD": {4: 1.5, 5: 2.0, 6: 2.0, 7: 2.0, 8: 1.5, 11: 0.5, 12: 0.5, 1: 0.5, 2: 0.5},
    "DECO": {11: 1.4, 12: 1.6},
    "BEDB": {1: 1.3, 10: 1.2, 11: 1.2},
    "WELL": {12: 1.5},
}

# -- Basket (what is bought) ------------------------------------------------
ITEMS_PER_ORDER = (1, 2, 3, 4, 5, 6, 7)
ITEMS_PER_ORDER_WEIGHTS = (35, 25, 16, 11, 7, 3.5, 2.5)  # mean ~2.5
QUANTITIES = (1, 2, 3, 4)
QUANTITY_WEIGHTS = (80, 15, 4, 1)
PRICE_DRIFT_PER_YEAR = 0.03  # prices were ~3% lower per year before the anchor
ITEM_DISCOUNT_SHARE = 0.10
ITEM_DISCOUNT_RATES = (Decimal("0.10"), Decimal("0.15"), Decimal("0.20"), Decimal("0.30"))
FREE_SHIPPING_THRESHOLD = Decimal("75.00")
SHIPPING_FEE = Decimal("7.99")

# -- Who buys and where it ships --------------------------------------------
GUEST_SHARE = 0.05
OTHER_ADDRESS_SHARE = 0.10  # registered customers shipping somewhere else (a gift)
CUSTOMER_ACTIVITY_ALPHA = 1.5  # Pareto shape: lower = more concentrated buying

# -- Payment and lifecycle --------------------------------------------------
PAYMENT_METHODS = ("credit_card", "debit_card", "paypal", "gift_card")
PAYMENT_METHOD_WEIGHTS = (60, 20, 15, 5)
PAYMENT_FAILED_SHARE = 0.03  # payment never succeeds: order cancelled
CANCELLED_AFTER_PAYMENT_SHARE = 0.04  # paid, then cancelled before shipment
PAYMENT_RETRY_SHARE = 0.07  # first attempt fails, the second succeeds

# -- Returns ----------------------------------------------------------------
ORDER_RETURN_SCALE = 1.15  # scales category return rates to ~24k returns
ITEM_IN_RETURN_SHARE = 0.6  # when an order is returned, share of its lines included
RETURN_REJECTED_SHARE = 0.08
RETURN_REASONS = (
    "damaged", "not_as_described", "changed_mind", "wrong_item", "too_large", "late_delivery",
)  # fmt: skip
RETURN_REASON_WEIGHTS = (25, 20, 25, 10, 12, 8)

HOUR = 3_600
DAY = 86_400


# ==========================================================================
# Public API
# ==========================================================================


@dataclass
class OrderBatch:
    """One calendar month of orders, ready to load."""

    month: str  # YYYY-MM
    orders: list[Order] = field(default_factory=list)
    order_items: list[OrderItem] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)


@dataclass
class ReturnsData:
    returns: list[Return]
    return_items: list[ReturnItem]


class OrderGenerator:
    """Generates the e-commerce transactions, one month at a time.

    Usage:
        generator = OrderGenerator(cfg, erp, customers)
        for batch in generator.monthly_batches():
            ...load batch...
        returns = generator.returns()   # after all batches
    """

    def __init__(self, cfg: GeneratorConfig, erp: ErpData, customers: CustomerData) -> None:
        self.cfg = cfg
        self.rng = cfg.rng("orders")
        self.fake = Faker("en_US")
        self.fake.seed_instance(self.rng.getrandbits(64))
        self.emails = EmailFactory(self.rng)

        self._products = _product_infos(self.rng, erp)
        self._pools: dict[tuple[int, int], tuple[list[_ProductInfo], list[float]]] = {}

        # Customers are sorted by signup (ids follow creation order), so the
        # customers who exist at a moment are always a prefix of the list.
        self._signups = [c.created_at for c in customers.ecommerce_customers]
        if self._signups != sorted(self._signups):
            raise ValueError("e-commerce customers must be sorted by created_at")
        activity = (
            min(self.rng.paretovariate(CUSTOMER_ACTIVITY_ALPHA), 100.0) for _ in self._signups
        )
        self._customer_cumulative = list(accumulate(activity))
        self._home: dict[int, tuple[str, str, str]] = {}  # customer index -> address
        self._buyers: set[int] = set()  # customers who already ordered

        self._state_codes = [s.code for s in US_STATES]
        self._state_weights = [s.population_m for s in US_STATES]
        self._tax_rate = {s.code: Decimal(str(s.sales_tax_pct)) / Decimal(100) for s in US_STATES}

        self._next_order_id = 1
        self._next_item_id = 1
        self._next_payment_id = 1
        self._pending_returns: list[_PendingReturn] = []

    def monthly_batches(self) -> Iterator[OrderBatch]:
        batch: OrderBatch | None = None
        for day, count in daily_order_counts(self.cfg, self.cfg.volumes.orders):
            month = f"{day:%Y-%m}"
            if batch is None or batch.month != month:
                if batch is not None:
                    yield batch
                batch = OrderBatch(month)
            moments = sorted(self._moment_in_day(day) for _ in range(count))
            for moment in moments:
                self._build_order(batch, moment)
        if batch is not None:
            yield batch

    def returns(self) -> ReturnsData:
        """Returns, with ids in request order (as the source system would assign them)."""
        pending = sorted(self._pending_returns, key=lambda r: (r.requested_at, r.order_id))
        returns: list[Return] = []
        items: list[ReturnItem] = []
        for return_id, entry in enumerate(pending, start=1):
            returns.append(
                Return(
                    return_id=return_id,
                    order_id=entry.order_id,
                    return_status=entry.status,
                    reason_code=entry.reason,
                    requested_at=as_utc(entry.requested_at),
                    refunded_at=as_utc(entry.refunded_at) if entry.refunded_at else None,
                    created_at=as_utc(entry.requested_at),
                    updated_at=as_utc(entry.updated_at),
                )
            )
            for order_item_id, quantity, refund in entry.items:
                items.append(
                    ReturnItem(
                        return_item_id=len(items) + 1,
                        return_id=return_id,
                        order_item_id=order_item_id,
                        quantity_returned=quantity,
                        refund_amount=refund,
                        created_at=as_utc(entry.requested_at),
                        updated_at=as_utc(entry.requested_at),
                    )
                )
        return ReturnsData(returns, items)

    # -- one order -----------------------------------------------------------

    def _build_order(self, batch: OrderBatch, moment: datetime) -> None:
        rng = self.rng
        order_id = self._next_order_id
        self._next_order_id += 1

        customer_index = None if rng.random() < GUEST_SHARE else self._pick_customer(moment)
        if customer_index is None:
            guest_email = self.emails.new(self.fake.first_name(), self.fake.last_name())
            city, state, postal_code = self._random_address()
            first_order = False
        else:
            guest_email = None
            city, state, postal_code = self._shipping_address(customer_index)
            first_order = customer_index not in self._buyers
            self._buyers.add(customer_index)

        # Lines: product, quantity, price and item discount
        products = self._pick_products(
            rng.choices(ITEMS_PER_ORDER, ITEMS_PER_ORDER_WEIGHTS)[0], moment
        )
        lines = []
        for product in products:
            quantity = rng.choices(QUANTITIES, QUANTITY_WEIGHTS)[0]
            unit_price = self._price_at(product, moment)
            gross = unit_price * quantity
            item_discount = ZERO
            if rng.random() < ITEM_DISCOUNT_SHARE:
                item_discount = money(gross * rng.choice(ITEM_DISCOUNT_RATES))
            lines.append((product, quantity, unit_price, item_discount, gross - item_discount))

        # Order coupon, allocated to the lines; tax on each line's net value
        bases = [line[4] for line in lines]
        coupon = self._coupon(moment.astimezone(LOCAL_TZ).date(), first_order)
        coupon_code, order_discount = None, ZERO
        if coupon is not None:
            coupon_code, coupon_rate = coupon
            order_discount = money(sum(bases) * coupon_rate)
        allocations = allocate_coupon(order_discount, bases)
        nets = [base - allocated for base, allocated in zip(bases, allocations, strict=True)]
        taxes = [money(net * self._tax_rate[state]) for net in nets]
        net_total = sum(nets, ZERO)
        shipping = ZERO if net_total >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE
        amount_due = net_total + sum(taxes, ZERO) + shipping

        lifecycle = self._lifecycle(moment)
        created = as_utc(moment)
        batch.orders.append(
            Order(
                order_id=order_id,
                order_number=f"ORD-{moment.astimezone(LOCAL_TZ).year}-{order_id:07d}",
                customer_id=None if customer_index is None else customer_index + 1,
                guest_email=guest_email,
                order_status=lifecycle.status,
                order_ts=created,
                coupon_code=coupon_code,
                order_discount_amount=order_discount,
                shipping_amount=shipping,
                ship_city=city,
                ship_state=state,
                ship_postal_code=postal_code,
                cancelled_at=as_utc(lifecycle.cancelled_at) if lifecycle.cancelled_at else None,
                created_at=created,
                updated_at=as_utc(lifecycle.updated_at),
            )
        )

        returnable = []
        for line_number, ((product, quantity, unit_price, item_discount, _), net, tax) in enumerate(
            zip(lines, nets, taxes, strict=True), start=1
        ):
            order_item_id = self._next_item_id
            self._next_item_id += 1
            batch.order_items.append(
                OrderItem(
                    order_item_id=order_item_id,
                    order_id=order_id,
                    line_number=line_number,
                    sku=product.sku,
                    quantity=quantity,
                    unit_price=unit_price,
                    item_discount_amount=item_discount,
                    tax_amount=tax,
                    created_at=created,
                    updated_at=created,
                )
            )
            returnable.append((order_item_id, quantity, net, product.parent))

        method = rng.choices(PAYMENT_METHODS, PAYMENT_METHOD_WEIGHTS)[0]
        for attempt, (payment_created, status, payment_updated) in enumerate(
            lifecycle.payments, start=1
        ):
            batch.payments.append(
                Payment(
                    payment_id=self._next_payment_id,
                    order_id=order_id,
                    attempt_number=attempt,
                    payment_method=method,
                    payment_status=status,
                    amount=amount_due,
                    provider_transaction_id=f"txn_{rng.getrandbits(64):016x}",
                    created_at=as_utc(payment_created),
                    updated_at=as_utc(payment_updated),
                )
            )
            self._next_payment_id += 1

        if lifecycle.delivered_at is not None:
            self._maybe_return(order_id, returnable, lifecycle.delivered_at)

    # -- choices -------------------------------------------------------------

    def _moment_in_day(self, day: date) -> datetime:
        hour = self.rng.choices(range(24), HOUR_WEIGHTS)[0]
        start = datetime.combine(day, time(hour), LOCAL_TZ)
        # Local wall-clock hour, then UTC for all further arithmetic (see timeutils)
        return as_utc(start + timedelta(seconds=self.rng.randrange(HOUR)))

    def _pick_customer(self, moment: datetime) -> int | None:
        """Weighted choice among the customers who already have an account."""
        existing = bisect_right(self._signups, moment)
        if existing == 0:
            return None
        target = self.rng.random() * self._customer_cumulative[existing - 1]
        return min(bisect_right(self._customer_cumulative, target), existing - 1)

    def _pick_products(self, count: int, moment: datetime) -> list[_ProductInfo]:
        """Distinct products that are on sale at that moment, weighted by popularity."""
        pool, cumulative = self._pool(moment)
        chosen: list[_ProductInfo] = []
        for _ in range(count * 20):
            if len(chosen) == count:
                break
            index = bisect_right(cumulative, self.rng.random() * cumulative[-1])
            product = pool[min(index, len(pool) - 1)]
            if product in chosen or product.launched > moment:
                continue
            if product.discontinued is not None and product.discontinued <= moment:
                continue
            chosen.append(product)
        return chosen or [pool[0]]

    def _pool(self, moment: datetime) -> tuple[list[_ProductInfo], list[float]]:
        """Products on sale during the month, with seasonal weights (cached per month)."""
        local = moment.astimezone(LOCAL_TZ)
        key = (local.year, local.month)
        if key not in self._pools:
            month_start = datetime(local.year, local.month, 1, tzinfo=LOCAL_TZ)
            month_end = (month_start + timedelta(days=32)).replace(day=1)
            pool = [
                p
                for p in self._products
                if p.launched < month_end
                and (p.discontinued is None or p.discontinued > month_start)
            ]
            weights = (
                p.popularity * SEASONAL_FACTORS.get(p.parent.code, {}).get(local.month, 1.0)
                for p in pool
            )
            self._pools[key] = (pool, list(accumulate(weights)))
        return self._pools[key]

    def _price_at(self, product: _ProductInfo, moment: datetime) -> Decimal:
        """Transactional price: the current list price, lower the further back in time."""
        years_before = (self.cfg.window_end - moment).days / 365.25
        value = float(product.list_price) * (1 - PRICE_DRIFT_PER_YEAR * years_before)
        return Decimal(max(int(value), 1)) + Decimal("0.99")

    def _shipping_address(self, customer_index: int) -> tuple[str, str, str]:
        if customer_index not in self._home:
            self._home[customer_index] = self._random_address()
        if self.rng.random() < OTHER_ADDRESS_SHARE:
            return self._random_address()
        return self._home[customer_index]

    def _random_address(self) -> tuple[str, str, str]:
        state = self.rng.choices(self._state_codes, self._state_weights)[0]
        return self.fake.city(), state, self.fake.zipcode_in_state(state)

    def _coupon(self, day: date, first_order: bool) -> tuple[str, Decimal] | None:
        """Seasonal campaigns, a welcome coupon and an always-on code."""
        rng = self.rng
        active = campaign(day)
        if active is not None:
            code, rate, probability = active
            if rng.random() < probability:
                return code, rate
        if first_order and rng.random() < 0.30:
            return "WELCOME10", Decimal("0.10")
        if rng.random() < 0.04:
            return "SAVE10", Decimal("0.10")
        return None

    # -- lifecycle -----------------------------------------------------------

    def _lifecycle(self, ordered: datetime) -> _Lifecycle:
        """Simulates the order's events and keeps the state as of the anchor date."""
        rng = self.rng
        roll = rng.random()
        attempt_at = ordered + self._seconds(5, 120)
        payments: list[tuple[datetime, list[tuple[datetime, str]]]] = []

        if roll < PAYMENT_FAILED_SHARE:
            for _ in range(2 if rng.random() < 0.4 else 1):
                failed_at = attempt_at + self._seconds(5, 60)
                payments.append((attempt_at, [(failed_at, "failed")]))
                attempt_at = failed_at + self._seconds(60, 600)
            cancelled_at = attempt_at + self._seconds(30 * 60, 2 * DAY)
            return self._resolve(ordered, [(cancelled_at, "cancelled")], payments, cancelled_at)

        if rng.random() < PAYMENT_RETRY_SHARE:
            failed_at = attempt_at + self._seconds(5, 60)
            payments.append((attempt_at, [(failed_at, "failed")]))
            attempt_at = failed_at + self._seconds(60, 600)
        captured_at = attempt_at + self._seconds(10, 900)

        if roll < PAYMENT_FAILED_SHARE + CANCELLED_AFTER_PAYMENT_SHARE:
            cancelled_at = captured_at + self._seconds(HOUR, 2 * DAY)
            refunded_at = cancelled_at + self._seconds(10 * 60, DAY)
            payments.append((attempt_at, [(captured_at, "captured"), (refunded_at, "refunded")]))
            events = [(captured_at, "paid"), (cancelled_at, "cancelled")]
            return self._resolve(ordered, events, payments, cancelled_at)

        shipped_at = captured_at + self._seconds(20 * HOUR, 3 * DAY)
        delivered_at = shipped_at + self._seconds(2 * DAY, 7 * DAY)
        payments.append((attempt_at, [(captured_at, "captured")]))
        events = [(captured_at, "paid"), (shipped_at, "shipped"), (delivered_at, "delivered")]
        return self._resolve(ordered, events, payments, delivered_at=delivered_at)

    def _resolve(
        self,
        ordered: datetime,
        events: list[tuple[datetime, str]],
        payments: list[tuple[datetime, list[tuple[datetime, str]]]],
        cancelled_at: datetime | None = None,
        delivered_at: datetime | None = None,
    ) -> _Lifecycle:
        """Keeps only what already happened at the end of the history."""
        end = self.cfg.window_end
        status, updated = _state_at(end, "pending_payment", ordered, events)
        payment_states = [
            (created, *_state_at(end, "authorized", created, payment_events))
            for created, payment_events in payments
            if created < end
        ]
        return _Lifecycle(
            status=status,
            updated_at=updated,
            cancelled_at=cancelled_at if status == "cancelled" else None,
            delivered_at=delivered_at if status == "delivered" else None,
            payments=payment_states,
        )

    def _maybe_return(
        self,
        order_id: int,
        lines: list[tuple[int, int, Decimal, ParentCategory]],
        delivered_at: datetime,
    ) -> None:
        """Decides whether a delivered order is (partly) returned, and which lines.

        The chance depends on the categories in the order; lines from categories
        with higher return rates are more likely to be part of the return.
        """
        rng = self.rng
        mean_rate = sum(parent.return_rate for *_, parent in lines) / len(lines)
        if rng.random() >= mean_rate * ORDER_RETURN_SCALE:
            return
        returned = []
        for order_item_id, quantity, net, parent in lines:
            if rng.random() < ITEM_IN_RETURN_SHARE * parent.return_rate / mean_rate:
                quantity_returned = rng.randint(1, quantity)
                refund = money(net / quantity * quantity_returned)  # net of tax
                returned.append((order_item_id, quantity_returned, refund))
        if not returned:  # at least one line: pick one at random
            order_item_id, quantity, net, _ = rng.choice(lines)
            quantity_returned = rng.randint(1, quantity)
            returned.append(
                (order_item_id, quantity_returned, money(net / quantity * quantity_returned))
            )
        requested_at = delivered_at + self._seconds(DAY, 30 * DAY)
        if requested_at >= self.cfg.window_end:
            return
        if rng.random() < RETURN_REJECTED_SHARE:
            events = [(requested_at + self._seconds(2 * DAY, 5 * DAY), "rejected")]
        else:
            approved_at = requested_at + self._seconds(DAY, 3 * DAY)
            received_at = approved_at + self._seconds(3 * DAY, 10 * DAY)
            refunded_at = received_at + self._seconds(DAY, 5 * DAY)
            events = [
                (approved_at, "approved"),
                (received_at, "received"),
                (refunded_at, "refunded"),
            ]
        status, updated = _state_at(self.cfg.window_end, "requested", requested_at, events)
        self._pending_returns.append(
            _PendingReturn(
                order_id=order_id,
                status=status,
                reason=rng.choices(RETURN_REASONS, RETURN_REASON_WEIGHTS)[0],
                requested_at=requested_at,
                refunded_at=updated if status == "refunded" else None,
                updated_at=updated,
                items=returned,
            )
        )

    def _seconds(self, low: int, high: int) -> timedelta:
        return timedelta(seconds=self.rng.randint(low, high))


# ==========================================================================
# Helpers
# ==========================================================================


def money(value: Decimal) -> Decimal:
    """Round to cents, half up (the usual commercial rounding)."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def allocate_coupon(order_discount: Decimal, bases: list[Decimal]) -> list[Decimal]:
    """Split an order coupon across items, proportionally to each item's base value.

    Same rule as docs/business/metrics-definition.md §3.2: shares are rounded
    to cents and the rounding residual goes to the item with the largest base
    (the first one, if several are tied), so the shares add up exactly.
    """
    total_base = sum(bases, ZERO)
    if order_discount == ZERO or total_base == ZERO:
        return [ZERO] * len(bases)
    shares = [money(order_discount * base / total_base) for base in bases]
    largest = max(range(len(bases)), key=lambda i: bases[i])
    shares[largest] += order_discount - sum(shares, ZERO)
    return shares


def daily_order_counts(cfg: GeneratorConfig, total: int) -> list[tuple[date, int]]:
    """Orders per day: growth x month seasonality x weekend x shopping events.

    Counts are proportional to the day weights and add up exactly to `total`
    (largest remainder method). This shape is deterministic: only the exact
    times and contents of the orders are random.
    """
    days = [
        cfg.history_start + timedelta(days=offset)
        for offset in range((cfg.anchor_date - cfg.history_start).days + 1)
    ]
    weights = [_day_weight(cfg, day) for day in days]
    scale = total / sum(weights)
    exact = [weight * scale for weight in weights]
    counts = [int(value) for value in exact]
    by_remainder = sorted(range(len(days)), key=lambda i: exact[i] - counts[i], reverse=True)
    for i in by_remainder[: total - sum(counts)]:
        counts[i] += 1
    return list(zip(days, counts, strict=True))


def _day_weight(cfg: GeneratorConfig, day: date) -> float:
    years = (day - cfg.history_start).days / 365.25
    weight = (1 + ANNUAL_GROWTH) ** years * MONTH_FACTORS[day.month]
    if day.weekday() >= 5:
        weight *= WEEKEND_FACTOR
    thanksgiving = _thanksgiving(day.year)
    event_factors = {
        thanksgiving: 0.8,
        thanksgiving + timedelta(days=1): 2.5,  # Black Friday
        thanksgiving + timedelta(days=2): 1.6,
        thanksgiving + timedelta(days=3): 1.6,
        thanksgiving + timedelta(days=4): 2.2,  # Cyber Monday
    }
    return weight * event_factors.get(day, 1.0)


def _thanksgiving(year: int) -> date:
    """Fourth Thursday of November."""
    november_first = date(year, 11, 1)
    first_thursday = november_first + timedelta(days=(3 - november_first.weekday()) % 7)
    return first_thursday + timedelta(weeks=3)


def campaign(day: date) -> tuple[str, Decimal, float] | None:
    """Coupon campaign active on a day: (code, discount rate, share of orders using it)."""
    thanksgiving = _thanksgiving(day.year)
    if thanksgiving + timedelta(days=1) <= day <= thanksgiving + timedelta(days=4):
        return "BFCM25", Decimal("0.25"), 0.45
    if day.month == 12 and day.day <= 24:
        return "HOLIDAY15", Decimal("0.15"), 0.25
    if day.month == 1 or (day.month == 2 and day.day <= 15):
        return "WINTER10", Decimal("0.10"), 0.15
    if (day.month == 3 and day.day >= 15) or day.month == 4:
        return "SPRING15", Decimal("0.15"), 0.12
    if (day.month == 6 and day.day >= 15) or day.month == 7:
        return "SUMMER20", Decimal("0.20"), 0.15
    return None


def _state_at(
    end: datetime, initial: str, start: datetime, events: list[tuple[datetime, str]]
) -> tuple[str, datetime]:
    """Status and last change time, considering only events before `end`."""
    status, changed = initial, start
    for moment, new_status in events:
        if moment >= end:
            break
        status, changed = new_status, moment
    return status, changed


@dataclass(frozen=True, slots=True, eq=False)
class _ProductInfo:
    sku: str
    list_price: Decimal
    parent: ParentCategory
    launched: datetime
    discontinued: datetime | None
    popularity: float


def _product_infos(rng: random.Random, erp: ErpData) -> list[_ProductInfo]:
    """What the order generator needs to know about each product."""
    parents_by_code = {p.code: p for p in CATALOG}
    category_codes = {c.category_id: c.category_code for c in erp.categories}
    parent_of_leaf = {
        c.category_id: parents_by_code[category_codes[c.parent_category_id]]
        for c in erp.categories
        if c.parent_category_id is not None
    }
    infos = []
    for product in erp.products:
        # Popularity: a few best-sellers, a long tail, and cheaper items sell more often
        popularity = rng.lognormvariate(0, 1.0) * float(product.list_price) ** -0.35
        infos.append(
            _ProductInfo(
                sku=product.sku,
                list_price=product.list_price,
                parent=parent_of_leaf[product.category_id],
                launched=product.created_at.replace(tzinfo=LOCAL_TZ),
                discontinued=None
                if product.is_active
                else product.updated_at.replace(tzinfo=LOCAL_TZ),
                popularity=popularity,
            )
        )
    return infos


@dataclass
class _Lifecycle:
    status: str
    updated_at: datetime
    cancelled_at: datetime | None
    delivered_at: datetime | None
    payments: list[tuple[datetime, str, datetime]]  # (created, status, updated) per attempt


@dataclass
class _PendingReturn:
    order_id: int
    status: str
    reason: str
    requested_at: datetime
    refunded_at: datetime | None
    updated_at: datetime
    items: list[tuple[int, int, Decimal]]  # (order_item_id, quantity_returned, refund_amount)
