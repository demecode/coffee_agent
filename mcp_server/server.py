from __future__ import annotations

import os
import uuid
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP


SERVER_HOST = os.getenv("HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PORT", "8000"))
TAX_RATE = 0.2

mcp = FastMCP(
    "coffee-mcp-server",
    instructions="Coffee shop tools for menus, recommendations, totals, store details, and mock orders.",
    host=SERVER_HOST,
    port=SERVER_PORT,
    sse_path="/sse",
    streamable_http_path="/mcp",
)

MENU: list[dict[str, Any]] = [
    {
        "id": "espresso",
        "name": "Espresso",
        "description": "Short, concentrated coffee with a rich crema.",
        "prices_gbp": {"single": 2.4, "double": 3.0},
        "tags": ["espresso-forward", "hot", "dairy-free"],
    },
    {
        "id": "americano",
        "name": "Americano",
        "description": "Espresso lengthened with hot water.",
        "prices_gbp": {"regular": 3.1, "large": 3.6},
        "tags": ["black coffee", "hot", "dairy-free"],
    },
    {
        "id": "latte",
        "name": "Latte",
        "description": "Espresso with steamed milk and a light foam top.",
        "prices_gbp": {"regular": 3.8, "large": 4.4},
        "tags": ["milk-forward", "hot"],
    },
    {
        "id": "flat-white",
        "name": "Flat White",
        "description": "Double espresso with velvety steamed milk.",
        "prices_gbp": {"regular": 3.7},
        "tags": ["espresso-forward", "milk-forward", "hot"],
    },
    {
        "id": "cappuccino",
        "name": "Cappuccino",
        "description": "Espresso with steamed milk and a thick foam cap.",
        "prices_gbp": {"regular": 3.7, "large": 4.2},
        "tags": ["milk-forward", "hot"],
    },
    {
        "id": "mocha",
        "name": "Mocha",
        "description": "Espresso, chocolate, steamed milk, and cocoa.",
        "prices_gbp": {"regular": 4.1, "large": 4.7},
        "tags": ["sweet", "milk-forward", "hot"],
    },
    {
        "id": "cold-brew",
        "name": "Cold Brew",
        "description": "Slow-steeped coffee served cold over ice.",
        "prices_gbp": {"regular": 3.9, "large": 4.5},
        "tags": ["iced", "black coffee", "dairy-free"],
    },
    {
        "id": "iced-latte",
        "name": "Iced Latte",
        "description": "Espresso, cold milk, and ice.",
        "prices_gbp": {"regular": 4.0, "large": 4.6},
        "tags": ["iced", "milk-forward"],
    },
]

MILK_OPTIONS = ["whole milk", "semi-skimmed milk", "oat milk", "almond milk", "soy milk", "coconut milk"]
SYRUPS = ["vanilla", "caramel", "hazelnut", "simple syrup"]

STORE = {
    "name": "Coffee Now London",
    "address": "42 Foundry Lane, London, UK",
    "timezone": "Europe/London",
    "currency": "GBP",
    "hours": {
        "monday-friday": "07:00-18:00",
        "saturday": "08:00-17:00",
        "sunday": "09:00-16:00",
    },
    "pickup_estimate_minutes": 12,
}


def _find_menu_item(item_id_or_name: str) -> dict[str, Any]:
    normalized = item_id_or_name.strip().lower()
    for item in MENU:
        if normalized in {item["id"], item["name"].lower()}:
            return item
    raise ValueError(f"Unknown menu item: {item_id_or_name}")


def _price_for(item: dict[str, Any], size: str) -> float:
    prices = item["prices_gbp"]
    if size in prices:
        return float(prices[size])
    if len(prices) == 1:
        return float(next(iter(prices.values())))
    available = ", ".join(prices.keys())
    raise ValueError(f"Size '{size}' is not available for {item['name']}. Available sizes: {available}")


@mcp.tool()
def get_menu(tag: str = "", limit: int = 8) -> dict[str, Any]:
    """Return coffee menu items, optionally filtered by a tag such as iced, sweet, milk-forward, or black coffee."""
    normalized_tag = tag.strip().lower()
    filtered = [item for item in MENU if not normalized_tag or normalized_tag in item["tags"]]
    return {
        "currency": "GBP",
        "filter": normalized_tag or "all",
        "milk_options": MILK_OPTIONS,
        "syrups": SYRUPS,
        "items": filtered[: max(1, min(limit, 20))],
    }


@mcp.tool()
def recommend_coffee(
    people: int = 1,
    drink_style: Literal[
        "espresso-forward",
        "milk-forward",
        "sweet",
        "iced",
        "black coffee",
        "mixed group",
        "not sure",
    ] = "not sure",
    caffeine_preference: Literal["regular", "strong", "low-caf", "decaf", "mixed", "not sure"] = "regular",
    milk_preference: Literal["dairy", "oat", "almond", "soy", "coconut", "black", "mixed", "not sure"] = "not sure",
    sweetness: Literal["unsweetened", "light", "medium", "sweet", "mixed", "not sure"] = "not sure",
    temperature: Literal["hot", "iced", "mixed", "not sure"] = "not sure",
) -> dict[str, Any]:
    """Recommend coffee drinks for one person or a group."""
    people = max(1, people)

    if drink_style == "espresso-forward":
        base = "Flat White" if milk_preference not in {"black", "not sure"} else "Americano"
    elif drink_style == "milk-forward":
        base = "Latte"
    elif drink_style == "sweet":
        base = "Mocha" if sweetness in {"medium", "sweet", "not sure"} else "Latte with vanilla"
    elif drink_style == "iced":
        base = "Iced Latte" if milk_preference != "black" else "Cold Brew"
    elif drink_style == "black coffee":
        base = "Americano" if temperature == "hot" else "Cold Brew"
    elif drink_style == "mixed group":
        return {
            "people": people,
            "recommendation": [
                {"drink": "Latte", "quantity": max(1, people // 2)},
                {"drink": "Americano", "quantity": max(1, people // 3)},
                {"drink": "Mocha", "quantity": people - max(1, people // 2) - max(1, people // 3)},
            ],
            "note": "Adjust quantities after asking who prefers black, milky, or sweet coffee.",
        }
    else:
        base = "Latte"

    modifiers = []
    if caffeine_preference == "strong":
        modifiers.append("extra shot")
    elif caffeine_preference == "low-caf":
        modifiers.append("half-caf")
    elif caffeine_preference == "decaf":
        modifiers.append("decaf")

    if milk_preference in {"oat", "almond", "soy", "coconut"}:
        modifiers.append(f"{milk_preference} milk")
    if sweetness in {"light", "medium", "sweet"}:
        modifiers.append(f"{sweetness} sweetness")
    if temperature == "iced" and not base.lower().startswith(("iced", "cold")):
        modifiers.append("iced")

    return {
        "people": people,
        "recommendation": [{"drink": base, "quantity": people, "modifiers": modifiers}],
        "note": "Default recommendation is one drink per person.",
    }


@mcp.tool()
def estimate_order_total(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate subtotal, tax, and total for order items. Each item needs item, quantity, and optional size."""
    line_items = []
    subtotal = 0.0

    for requested in items:
        menu_item = _find_menu_item(str(requested["item"]))
        quantity = int(requested.get("quantity", 1))
        size = str(requested.get("size", next(iter(menu_item["prices_gbp"].keys()))))
        unit_price = _price_for(menu_item, size)
        line_total = round(unit_price * quantity, 2)
        subtotal += line_total
        line_items.append(
            {
                "item": menu_item["name"],
                "size": size,
                "quantity": quantity,
                "unit_price_gbp": unit_price,
                "line_total_gbp": line_total,
            }
        )

    subtotal = round(subtotal, 2)
    tax = round(subtotal * TAX_RATE, 2)
    total = round(subtotal + tax, 2)
    return {"currency": "GBP", "line_items": line_items, "subtotal": subtotal, "tax": tax, "total": total}


@mcp.tool()
def get_store_info() -> dict[str, Any]:
    """Return mock store address, timezone, hours, and pickup estimate."""
    return STORE


@mcp.tool()
def create_order(customer_name: str, items: list[dict[str, Any]], confirmed: bool = False) -> dict[str, Any]:
    """Create a mock coffee order. The caller must set confirmed=true after the user confirms the order."""
    if not confirmed:
        return {
            "status": "needs_confirmation",
            "message": "Confirm the full order with the customer before creating it.",
        }

    total = estimate_order_total(items)
    return {
        "status": "created",
        "order_id": f"COF-{uuid.uuid4().hex[:8].upper()}",
        "customer_name": customer_name,
        "pickup_estimate_minutes": STORE["pickup_estimate_minutes"],
        "total": total,
    }


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    if transport not in {"sse", "streamable-http", "stdio"}:
        raise ValueError("MCP_TRANSPORT must be one of: sse, streamable-http, stdio")
    mcp.run(transport=transport)
