"""Static business reference data: product hierarchy, brands and naming vocabulary.

Cost ratios and return rates are per top-level category, so that margin and
return-rate analyses show realistic differences between categories.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeafCategory:
    code: str
    name: str
    noun: str  # used to build product names
    price_low: int  # list price range, USD
    price_high: int


@dataclass(frozen=True)
class ParentCategory:
    code: str
    name: str
    cost_ratio: float  # typical unit cost / list price
    return_rate: float  # share of delivered items returned
    materials: tuple[str, ...]
    leaves: tuple[LeafCategory, ...]


# Table-like layout kept on purpose: the formatter is disabled for this block.
# fmt: off
CATALOG: tuple[ParentCategory, ...] = (
    ParentCategory(
        "FURN", "Furniture", 0.45, 0.06,
        ("Oak", "Walnut", "Teak", "Velvet", "Leather", "Rattan"),
        (
            LeafCategory("FURN-SOFA", "Sofas & Sectionals", "Sofa", 499, 2499),
            LeafCategory("FURN-TABL", "Dining Tables", "Dining Table", 299, 1499),
            LeafCategory("FURN-CHAI", "Chairs & Stools", "Chair", 79, 399),
            LeafCategory("FURN-SHEL", "Bookcases & Shelving", "Bookcase", 99, 599),
        ),
    ),
    ParentCategory(
        "KITC", "Kitchen & Dining", 0.40, 0.04,
        ("Stainless", "Cast Iron", "Ceramic", "Stoneware", "Copper", "Bamboo"),
        (
            LeafCategory("KITC-COOK", "Cookware", "Skillet", 29, 249),
            LeafCategory("KITC-DINN", "Dinnerware", "Dinner Plate Set", 29, 179),
            LeafCategory("KITC-GLAS", "Glassware", "Glass Set", 19, 99),
            LeafCategory("KITC-UTEN", "Utensils & Gadgets", "Utensil Set", 9, 59),
        ),
    ),
    ParentCategory(
        "BEDB", "Bedding & Bath", 0.35, 0.09,
        ("Linen", "Cotton", "Bamboo", "Flannel", "Percale", "Sateen"),
        (
            LeafCategory("BEDB-SHEE", "Sheets", "Sheet Set", 49, 249),
            LeafCategory("BEDB-DUVE", "Duvets & Comforters", "Duvet", 89, 399),
            LeafCategory("BEDB-TOWE", "Towels", "Towel Set", 19, 119),
            LeafCategory("BEDB-PILL", "Pillows", "Pillow", 25, 129),
        ),
    ),
    ParentCategory(
        "DECO", "Home Decor", 0.30, 0.07,
        ("Brass", "Marble", "Ceramic", "Jute", "Glass", "Wool"),
        (
            LeafCategory("DECO-WALL", "Wall Art", "Wall Print", 39, 299),
            LeafCategory("DECO-MIRR", "Mirrors", "Mirror", 59, 399),
            LeafCategory("DECO-VASE", "Vases & Planters", "Vase", 19, 129),
            LeafCategory("DECO-RUGS", "Rugs", "Area Rug", 79, 899),
        ),
    ),
    ParentCategory(
        "LIGH", "Lighting", 0.40, 0.08,
        ("Brass", "Matte Black", "Glass", "Rattan", "Linen", "Ceramic"),
        (
            LeafCategory("LIGH-TABL", "Table Lamps", "Table Lamp", 39, 249),
            LeafCategory("LIGH-FLOO", "Floor Lamps", "Floor Lamp", 79, 399),
            LeafCategory("LIGH-PEND", "Pendants", "Pendant Light", 69, 449),
            LeafCategory("LIGH-OUTD", "Outdoor Lighting", "String Lights", 19, 149),
        ),
    ),
    ParentCategory(
        "OUTD", "Outdoor & Garden", 0.45, 0.05,
        ("Teak", "Acacia", "Aluminum", "Terracotta", "Steel", "Resin"),
        (
            LeafCategory("OUTD-FURN", "Patio Furniture", "Patio Chair", 99, 1299),
            LeafCategory("OUTD-PLAN", "Planters & Pots", "Planter", 19, 149),
            LeafCategory("OUTD-GRIL", "Grilling", "Grill Tool Set", 29, 299),
            LeafCategory("OUTD-TOOL", "Garden Tools", "Garden Tool Set", 15, 99),
        ),
    ),
    ParentCategory(
        "STOR", "Storage & Organization", 0.35, 0.04,
        ("Seagrass", "Bamboo", "Canvas", "Wire", "Acacia", "Felt"),
        (
            LeafCategory("STOR-BASK", "Baskets & Bins", "Storage Basket", 15, 79),
            LeafCategory("STOR-CLOS", "Closet Systems", "Closet Organizer", 49, 399),
            LeafCategory("STOR-KITC", "Kitchen Storage", "Canister Set", 19, 89),
            LeafCategory("STOR-HOOK", "Hooks & Racks", "Wall Rack", 12, 79),
        ),
    ),
    ParentCategory(
        "WELL", "Wellness & Personal Care", 0.30, 0.03,
        ("Soy", "Lavender", "Eucalyptus", "Cedarwood", "Cotton", "Waffle"),
        (
            LeafCategory("WELL-CAND", "Candles & Diffusers", "Candle", 12, 69),
            LeafCategory("WELL-BATH", "Bath Accessories", "Bath Caddy", 15, 89),
            LeafCategory("WELL-ROBE", "Spa & Robes", "Bath Robe", 39, 149),
            LeafCategory("WELL-AROM", "Aromatherapy", "Essential Oil Set", 15, 79),
        ),
    ),
)

# fmt: on

# Fictional brands. "Cedar & Co." is the retailer's own label.
BRANDS: tuple[str, ...] = (
    "Cedar & Co.",
    "Northfield Home",
    "Willow & Stone",
    "Maple Row",
    "Bramble House",
    "Ironwood Living",
    "Linen Loft",
    "Copper Kettle Goods",
    "Blue Fern",
    "Saltbox Studio",
)

STYLES: tuple[str, ...] = (
    "Classic",
    "Modern",
    "Rustic",
    "Coastal",
    "Nordic",
    "Vintage",
    "Minimal",
    "Heritage",
    "Urban",
    "Studio",
)

# Reserved example domains (RFC 2606): generated emails can never reach a real mailbox.
EMAIL_DOMAINS: tuple[str, ...] = ("example.com", "example.net", "example.org")

CRM_SEGMENTS: tuple[str, ...] = ("bronze", "silver", "gold", "platinum")
CRM_SEGMENT_WEIGHTS: tuple[float, ...] = (0.50, 0.30, 0.15, 0.05)
