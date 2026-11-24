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


@dataclass(frozen=True)
class UsState:
    code: str
    name: str
    population_m: float  # approximate population in millions: weights where orders ship to
    sales_tax_pct: float  # simplified state-level base rate; local taxes are ignored


# fmt: off
US_STATES: tuple[UsState, ...] = (
    UsState("AL", "Alabama", 5.0, 4.0),          UsState("AK", "Alaska", 0.7, 0.0),
    UsState("AZ", "Arizona", 7.2, 5.6),          UsState("AR", "Arkansas", 3.0, 6.5),
    UsState("CA", "California", 39.5, 7.25),     UsState("CO", "Colorado", 5.8, 2.9),
    UsState("CT", "Connecticut", 3.6, 6.35),     UsState("DE", "Delaware", 1.0, 0.0),
    UsState("DC", "District of Columbia", 0.7, 6.0), UsState("FL", "Florida", 21.5, 6.0),
    UsState("GA", "Georgia", 10.7, 4.0),         UsState("HI", "Hawaii", 1.5, 4.0),
    UsState("ID", "Idaho", 1.8, 6.0),            UsState("IL", "Illinois", 12.8, 6.25),
    UsState("IN", "Indiana", 6.8, 7.0),          UsState("IA", "Iowa", 3.2, 6.0),
    UsState("KS", "Kansas", 2.9, 6.5),           UsState("KY", "Kentucky", 4.5, 6.0),
    UsState("LA", "Louisiana", 4.7, 4.45),       UsState("ME", "Maine", 1.4, 5.5),
    UsState("MD", "Maryland", 6.2, 6.0),         UsState("MA", "Massachusetts", 7.0, 6.25),
    UsState("MI", "Michigan", 10.1, 6.0),        UsState("MN", "Minnesota", 5.7, 6.875),
    UsState("MS", "Mississippi", 3.0, 7.0),      UsState("MO", "Missouri", 6.2, 4.225),
    UsState("MT", "Montana", 1.1, 0.0),          UsState("NE", "Nebraska", 2.0, 5.5),
    UsState("NV", "Nevada", 3.1, 6.85),          UsState("NH", "New Hampshire", 1.4, 0.0),
    UsState("NJ", "New Jersey", 9.3, 6.625),     UsState("NM", "New Mexico", 2.1, 5.0),
    UsState("NY", "New York", 20.2, 4.0),        UsState("NC", "North Carolina", 10.4, 4.75),
    UsState("ND", "North Dakota", 0.8, 5.0),     UsState("OH", "Ohio", 11.8, 5.75),
    UsState("OK", "Oklahoma", 4.0, 4.5),         UsState("OR", "Oregon", 4.2, 0.0),
    UsState("PA", "Pennsylvania", 13.0, 6.0),    UsState("RI", "Rhode Island", 1.1, 7.0),
    UsState("SC", "South Carolina", 5.1, 6.0),   UsState("SD", "South Dakota", 0.9, 4.2),
    UsState("TN", "Tennessee", 6.9, 7.0),        UsState("TX", "Texas", 29.1, 6.25),
    UsState("UT", "Utah", 3.3, 6.1),             UsState("VT", "Vermont", 0.6, 6.0),
    UsState("VA", "Virginia", 8.6, 5.3),         UsState("WA", "Washington", 7.7, 6.5),
    UsState("WV", "West Virginia", 1.8, 6.0),    UsState("WI", "Wisconsin", 5.9, 5.0),
    UsState("WY", "Wyoming", 0.6, 4.0),
)
# fmt: on
