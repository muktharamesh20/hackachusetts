"""Nutrition + aggregate reporting helpers over inventory items."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from pantrysort.inventory.models import FoodCategory, InventoryItem


@dataclass
class NutritionSummary:
    total_items: int
    total_units: int
    total_calories: int
    calories_known_units: int   # units whose calorie value was known
    by_category_units: dict[FoodCategory, int]
    by_category_calories: dict[FoodCategory, int]

    @property
    def average_calories_per_unit(self) -> float:
        if self.calories_known_units == 0:
            return 0.0
        return self.total_calories / self.calories_known_units


def summarize(items: Iterable[InventoryItem]) -> NutritionSummary:
    """Aggregate calories and counts across a collection of items."""
    total_items = 0
    total_units = 0
    total_calories = 0
    calories_known_units = 0
    by_cat_units: dict[FoodCategory, int] = defaultdict(int)
    by_cat_cal: dict[FoodCategory, int] = defaultdict(int)

    for item in items:
        total_items += 1
        total_units += item.quantity
        by_cat_units[item.category] += item.quantity
        if item.unit_calories is not None:
            cal = item.unit_calories * item.quantity
            total_calories += cal
            calories_known_units += item.quantity
            by_cat_cal[item.category] += cal

    return NutritionSummary(
        total_items=total_items,
        total_units=total_units,
        total_calories=total_calories,
        calories_known_units=calories_known_units,
        by_category_units=dict(by_cat_units),
        by_category_calories=dict(by_cat_cal),
    )


def estimate_servings(total_calories: int, calories_per_serving: int = 2000) -> float:
    """Rough estimate of daily food-servings (default 2000 kcal/day)."""
    if calories_per_serving <= 0:
        raise ValueError("calories_per_serving must be positive")
    return total_calories / calories_per_serving


def fefo_order(
    items: Iterable[InventoryItem], today: date | None = None
) -> list[InventoryItem]:
    """First-Expired-First-Out ordering.

    Items with an expiration date come first (soonest expiry first); items
    without a known expiry sort last.
    """
    today = today or date.today()
    far_future = 10**9

    def key(item: InventoryItem) -> int:
        days = item.days_until_expiry(today)
        return days if days is not None else far_future

    return sorted(items, key=key)
