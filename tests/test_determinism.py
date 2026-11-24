"""Reproducibility: the same seed always produces the same data."""

from __future__ import annotations

from dataclasses import astuple, fields

from tests.conftest import Dataset, build_dataset


def snapshot(data: Dataset) -> dict[str, list[tuple]]:
    """Every row of every table, as plain tuples."""
    tables = {
        "categories": data.erp.categories,
        "products": data.erp.products,
        "costs": data.erp.costs,
        "crm_customers": data.customers.crm_customers,
        "crm_contacts": data.customers.crm_contacts,
        "customers": data.customers.ecommerce_customers,
    }
    tables.update({f.name: getattr(data, f.name) for f in fields(data)[3:]})
    return {name: [astuple(row) for row in rows] for name, rows in tables.items()}


def test_same_seed_gives_identical_data(dataset: Dataset) -> None:
    assert snapshot(build_dataset(seed=7)) == snapshot(dataset)


def test_different_seed_gives_different_data(dataset: Dataset) -> None:
    assert snapshot(build_dataset(seed=8))["orders"] != snapshot(dataset)["orders"]


def test_quality_issues_do_not_change_which_orders_exist(clean: Dataset, dataset: Dataset) -> None:
    """The issues use their own random stream: same orders, same totals."""
    assert [(o.order_id, o.order_ts, o.order_status) for o in clean.orders] == [
        (o.order_id, o.order_ts, o.order_status) for o in dataset.orders
    ]
