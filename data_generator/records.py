"""Row types: one dataclass per source table.

Field names and order match the table columns in infrastructure/postgres/init/,
so a record can be loaded with COPY without any mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime
from decimal import Decimal
from functools import cache

# --------------------------------------------------------------------------
# ERP (local time, no time zone)
# --------------------------------------------------------------------------


@dataclass(slots=True)
class ProductCategory:
    category_id: int
    category_code: str
    category_name: str
    parent_category_id: int | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Product:
    product_id: int
    sku: str
    product_name: str
    category_id: int
    brand: str | None
    list_price: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ProductCost:
    cost_id: int
    product_id: int
    unit_cost: Decimal
    valid_from: date
    valid_to: date | None  # exclusive; None = current cost
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# CRM (local time, no time zone)
# --------------------------------------------------------------------------


@dataclass(slots=True)
class CrmCustomer:
    crm_customer_id: str
    full_name: str
    segment: str
    status: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class CrmContact:
    contact_id: int
    crm_customer_id: str
    contact_type: str
    contact_value: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# E-commerce (timestamptz, UTC)
# --------------------------------------------------------------------------


@dataclass(slots=True)
class Customer:
    customer_id: int
    email: str
    first_name: str
    last_name: str
    phone: str | None
    crm_customer_ref: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Order:
    order_id: int
    order_number: str
    customer_id: int | None
    guest_email: str | None
    order_status: str
    order_ts: datetime
    coupon_code: str | None
    order_discount_amount: Decimal
    shipping_amount: Decimal
    ship_city: str
    ship_state: str
    ship_postal_code: str | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class OrderItem:
    order_item_id: int
    order_id: int
    line_number: int
    sku: str
    quantity: int
    unit_price: Decimal
    item_discount_amount: Decimal
    tax_amount: Decimal
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Payment:
    payment_id: int
    order_id: int
    attempt_number: int
    payment_method: str
    payment_status: str
    amount: Decimal
    provider_transaction_id: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Return:
    return_id: int
    order_id: int
    return_status: str
    reason_code: str
    requested_at: datetime
    refunded_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ReturnItem:
    return_item_id: int
    return_id: int
    order_item_id: int
    quantity_returned: int
    refund_amount: Decimal  # net of tax
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


@cache
def column_names(record_type: type) -> tuple[str, ...]:
    """Column names of a record type, in table order."""
    return tuple(f.name for f in fields(record_type))


def row_values(record: object) -> tuple:
    """Values of a record, in column order."""
    return tuple(getattr(record, name) for name in column_names(type(record)))
