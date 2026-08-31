"""
Flexible business-type presets for catalog onboarding.
These are suggestions only — shopkeepers can add any product with any attributes.
"""
from typing import Any, Dict, List, Optional

BUSINESS_TYPES: Dict[str, Dict[str, Any]] = {
    "Kirana & Retail": {
        "label": "🏪 Kirana & Retail",
        "default_categories": ["Groceries", "Snacks", "Beverages", "Household"],
        "default_units": ["kg", "gram", "packet", "piece", "litre"],
        "attribute_hints": ["Brand", "Weight", "Expiry Date"],
        "sample_items": [
            {"name": "atta", "price": 55, "category": "Groceries", "unit": "kg"},
            {"name": "milk", "price": 60, "category": "Beverages", "unit": "litre"},
        ],
    },
    "Cafe & Restaurant": {
        "label": "🍽️ Cafe & Restaurant",
        "default_categories": ["Beverages", "Snacks", "Main Course", "Desserts"],
        "default_units": ["cup", "glass", "plate", "piece"],
        "attribute_hints": ["Dietary", "Spice Level", "Portion"],
        "sample_items": [
            {"name": "masala chai", "price": 20, "category": "Beverages", "unit": "cup"},
            {"name": "veg sandwich", "price": 80, "category": "Snacks", "unit": "piece"},
        ],
    },
    "Pharmacy": {
        "label": "💊 Pharmacy",
        "default_categories": ["Medicines", "OTC", "Personal Care"],
        "default_units": ["strip", "bottle", "tube", "piece"],
        "attribute_hints": ["Dosage", "Manufacturer", "Expiry Date", "Rx Required"],
        "sample_items": [
            {"name": "paracetamol 650", "price": 30, "category": "Medicines", "unit": "strip"},
        ],
    },
    "Fruits & Vegetables": {
        "label": "🍎 Fruits & Vegetables",
        "default_categories": ["Fruits", "Vegetables", "Organic"],
        "default_units": ["kg", "gram", "piece", "dozen"],
        "attribute_hints": ["Origin", "Organic", "Shelf Life"],
        "sample_items": [
            {"name": "banana", "price": 60, "category": "Fruits", "unit": "dozen"},
        ],
    },
    "Stationery": {
        "label": "📚 Stationery",
        "default_categories": ["Stationery", "Books", "Printing"],
        "default_units": ["piece", "packet", "box"],
        "attribute_hints": ["Brand", "Pages", "Size"],
        "sample_items": [
            {"name": "notebook", "price": 50, "category": "Stationery", "unit": "piece"},
        ],
    },
    "Apparel": {
        "label": "👕 Apparel",
        "default_categories": ["Men", "Women", "Kids", "Accessories"],
        "default_units": ["piece"],
        "attribute_hints": ["Size", "Color", "Fabric"],
        "sample_items": [
            {"name": "cotton t-shirt", "price": 499, "category": "Men", "unit": "piece"},
        ],
    },
    "Hardware": {
        "label": "🔩 Hardware",
        "default_categories": ["Tools", "Electrical", "Plumbing", "Paint"],
        "default_units": ["piece", "meter", "kg", "litre"],
        "attribute_hints": ["Material", "Dimensions", "Brand"],
        "sample_items": [
            {"name": "screwdriver set", "price": 250, "category": "Tools", "unit": "piece"},
        ],
    },
    "Custom": {
        "label": "✨ Custom / Other",
        "default_categories": ["General"],
        "default_units": ["piece", "kg", "packet"],
        "attribute_hints": [],
        "sample_items": [],
    },
}


def get_business_preset(business_type: Optional[str]) -> Dict[str, Any]:
    if business_type and business_type in BUSINESS_TYPES:
        return BUSINESS_TYPES[business_type]
    return BUSINESS_TYPES["Custom"]


def list_business_types() -> List[Dict[str, str]]:
    return [{"id": k, "label": v["label"]} for k, v in BUSINESS_TYPES.items()]
