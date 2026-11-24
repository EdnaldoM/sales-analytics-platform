"""Historical load: rebuild the three source databases from scratch.

Every run empties the tables first, so `make seed` can be repeated safely and
always ends in the same state for the same seed and anchor date.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections.abc import Sequence

from data_generator import db, reference
from data_generator.config import GeneratorConfig
from data_generator.orders import OrderGenerator

log = logging.getLogger(__name__)

# Children first: the order does not matter for TRUNCATE ... CASCADE, but it documents the FKs.
ERP_TABLES = ("product_cost_history", "products", "product_categories")
CRM_TABLES = ("customer_contacts", "customers")
ECOMMERCE_TABLES = ("return_items", "returns", "payments", "order_items", "orders", "customers")


def run(cfg: GeneratorConfig) -> None:
    started = time.perf_counter()
    log.info("Seed %s, history %s to %s", cfg.seed, cfg.history_start.isoformat(), cfg.anchor_date)

    erp = reference.generate_erp(cfg)
    customers = reference.generate_customers(cfg)
    log.info("Generated reference data in %.1fs", time.perf_counter() - started)

    # Parents before children: foreign keys are checked row by row during COPY.
    _load(
        "erp",
        ERP_TABLES,
        [
            ("product_categories", erp.categories, "category_id"),
            ("products", erp.products, "product_id"),
            ("product_cost_history", erp.costs, "cost_id"),
        ],
    )
    _load(
        "crm",
        CRM_TABLES,
        [
            ("customers", customers.crm_customers, None),  # text ids, no sequence
            ("customer_contacts", customers.crm_contacts, "contact_id"),
        ],
    )
    _load_ecommerce(OrderGenerator(cfg, erp, customers), customers.ecommerce_customers)
    log.info("Seed finished in %.1fs", time.perf_counter() - started)


def _load(
    dbname: str,
    tables_to_empty: Sequence[str],
    loads: Sequence[tuple[str, Sequence[object], str | None]],
) -> None:
    """Empty and reload one database in a single transaction."""
    with db.connect(dbname) as conn:
        db.truncate(conn, tables_to_empty)
        for table, records, id_column in loads:
            count = db.copy_records(conn, table, records)
            if id_column:
                db.sync_identity(conn, table, id_column)
            log.info("Loaded %s.%s: %s rows", dbname, table, f"{count:,}")


def _load_ecommerce(generator: OrderGenerator, ecommerce_customers: Sequence[object]) -> None:
    """Customers, then orders month by month, then returns: one transaction."""
    with db.connect("ecommerce") as conn:
        db.truncate(conn, ECOMMERCE_TABLES)
        count = db.copy_records(conn, "customers", ecommerce_customers)
        log.info("Loaded ecommerce.customers: %s rows", f"{count:,}")

        totals: Counter[str] = Counter()
        for batch in generator.monthly_batches():
            totals["orders"] += db.copy_records(conn, "orders", batch.orders)
            totals["order_items"] += db.copy_records(conn, "order_items", batch.order_items)
            totals["payments"] += db.copy_records(conn, "payments", batch.payments)
            log.info(
                "Loaded %s: %s orders, %s items",
                batch.month,
                f"{len(batch.orders):,}",
                f"{len(batch.order_items):,}",
            )

        returns = generator.returns()
        totals["returns"] = db.copy_records(conn, "returns", returns.returns)
        totals["return_items"] = db.copy_records(conn, "return_items", returns.return_items)

        for table, id_column in (
            ("customers", "customer_id"),
            ("orders", "order_id"),
            ("order_items", "order_item_id"),
            ("payments", "payment_id"),
            ("returns", "return_id"),
            ("return_items", "return_item_id"),
        ):
            db.sync_identity(conn, table, id_column)
        for table, count in totals.items():
            log.info("Loaded ecommerce.%s: %s rows", table, f"{count:,}")
