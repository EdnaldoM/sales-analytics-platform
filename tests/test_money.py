"""Money and calendar rules (docs/business/metrics-definition.md)."""

from __future__ import annotations

from decimal import Decimal

from data_generator.config import GeneratorConfig
from data_generator.orders import _thanksgiving, allocate_coupon, daily_order_counts


def d(value: str) -> Decimal:
    return Decimal(value)


def test_coupon_shares_add_up_to_the_discount() -> None:
    shares = allocate_coupon(d("10.00"), [d("33.33"), d("33.33"), d("33.34")])
    assert sum(shares) == d("10.00")


def test_coupon_is_proportional_to_each_base() -> None:
    assert allocate_coupon(d("10.00"), [d("75.00"), d("25.00")]) == [d("7.50"), d("2.50")]


def test_coupon_rounding_residual_goes_to_the_largest_base() -> None:
    # Rounded shares are 0.32 + 0.32 + 0.35 = 0.99; the missing cent goes to the largest item
    assert allocate_coupon(d("1.00"), [d("10.00"), d("10.00"), d("11.00")]) == [
        d("0.32"),
        d("0.32"),
        d("0.36"),
    ]
    assert allocate_coupon(d("1.00"), [d("10.00"), d("10.00"), d("10.00")]) == [
        d("0.34"),  # tie: the first of the largest items
        d("0.33"),
        d("0.33"),
    ]


def test_no_coupon_means_no_allocation() -> None:
    assert allocate_coupon(d("0.00"), [d("10.00"), d("20.00")]) == [d("0.00"), d("0.00")]


def test_daily_counts_add_up_to_the_requested_total() -> None:
    cfg = GeneratorConfig()
    counts = daily_order_counts(cfg, 400_000)
    assert sum(count for _, count in counts) == 400_000
    assert counts[0][0] == cfg.history_start
    assert counts[-1][0] == cfg.anchor_date


def test_black_friday_is_busier_than_thanksgiving() -> None:
    counts = dict(daily_order_counts(GeneratorConfig(), 400_000))
    thanksgiving = _thanksgiving(2025)
    black_friday = thanksgiving.replace(day=thanksgiving.day + 1)
    assert counts[black_friday] > 2 * counts[thanksgiving]
