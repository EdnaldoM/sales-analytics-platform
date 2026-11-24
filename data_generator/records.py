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
