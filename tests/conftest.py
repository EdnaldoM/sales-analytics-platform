"""Shared test data: a small dataset generated in memory, without a database.

pytest loads conftest.py automatically. A fixture is a function whose result
is passed to every test that names it as a parameter; scope="session" builds
it once for the whole test run.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from data_generator import reference
from data_generator.config import GeneratorConfig, Volumes
from data_generator.orders import OrderGenerator
from data_generator.quality import QualityInjector
from data_generator.records import Order, OrderItem, Payment, Return, ReturnItem

SMALL = Volumes(ecommerce_customers=1_000, crm_leads=100, products=200, orders=5_000)


@dataclass
class Dataset:
    """Everything `make seed` would load, kept in memory."""

    cfg: GeneratorConfig
    erp: reference.ErpData
    customers: reference.CustomerData
    orders: list[Order]
    order_items: list[OrderItem]
    payments: list[Payment]
    returns: list[Return]
    return_items: list[ReturnItem]


def build_dataset(seed: int = 7, inject_issues: bool = True) -> Dataset:
    """Same steps as seed.run, minus the database."""
    cfg = GeneratorConfig(seed=seed, volumes=SMALL)
    erp = reference.generate_erp(cfg)
    customers = reference.generate_customers(cfg)
    generator = OrderGenerator(cfg, erp, customers)
    quality = QualityInjector(cfg)
    if inject_issues:
        quality.apply_to_reference(erp, customers)

    orders, items, payments = [], [], []
    for batch in generator.monthly_batches():
        if inject_issues:
            quality.apply_to_batch(batch)
        orders += batch.orders
        items += batch.order_items
        payments += batch.payments
    returns = generator.returns()
    return Dataset(
        cfg, erp, customers, orders, items, payments, returns.returns, returns.return_items
    )


@pytest.fixture(scope="session")
def clean() -> Dataset:
    """Data before the quality issues: business rules must hold exactly."""
    return build_dataset(inject_issues=False)


@pytest.fixture(scope="session")
def dataset() -> Dataset:
    """Data as loaded into the sources, quality issues included."""
    return build_dataset()
