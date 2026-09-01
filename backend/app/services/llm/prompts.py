import json
from typing import Optional, List


def build_extraction_prompt(
    text: str,
    catalog_items: Optional[List[str]] = None,
    merchant_profile: Optional[dict] = None,
    business_type: Optional[str] = None,
    context: str = "terminal",
) -> str:
    """
    Constructs the prompt for extracting structured transactional intent, items, and pricing.
    """
    catalog_prompt = (
        f"Merchant Store Product Catalog (Known Items): {', '.join(catalog_items)}. (The merchant can also sell new items dynamically)."
        if catalog_items
        else "Merchant Store Product Catalog: Open Catalog Mode (any product spoken by the merchant will be sold and auto-registered)."
    )
    profile_prompt = f"Merchant Profile: {json.dumps(merchant_profile, default=str)}" if merchant_profile else ""
    business_prompt = f"Business Type: {business_type}" if business_type else ""
    context_hint = (
        "Context: catalog management tab — prioritize add_to_catalog, list_catalog, search_catalog intents."
        if context == "catalog"
        else "Context: store sales and payment terminal."
    )

    return f"""
You are VoiceLedger AI, an intelligent transactional voice agent for Indian shopkeepers and retail merchants.
Analyze what the merchant spoke or typed in Hindi, Hinglish, or English:
"{text}"

{catalog_prompt}
{profile_prompt}
{business_prompt}
{context_hint}

STRICT AGENT INSTRUCTIONS:
- Open Catalog Ordering: Whenever the merchant speaks items, quantities, or prices (e.g. "2 coffee 60 rs", "Add Burger (₹100)", "3 notebook 150", "2 samosa 30 rupaye"), ALWAYS set intent to "record_sale" and extract the items and pricing. Do NOT reject or ask to add to catalog first!
- Classify the merchant's exact intent accurately:
  * "record_sale": Default when items/quantities/prices are spoken on the sales terminal (e.g., "2 coffee 60 rs", "Add Burger (₹100)", "3 notebook 150", "2 coffee aur 1 sandwich 120 rupaye", "Ramesh ka 2 chai 20 rs baaki").
  * "add_to_catalog": Explicitly adding a new item to store menu/catalog (e.g., "Menu mein burger add karo 100 rupaye", "Catalog mein samosa dalo").
  * "check_payment_status": Checking whether a payment arrived or checking order payment state (e.g., "Payment aaya kya?", "Burger ka payment hua?", "Check payment").
  * "query_pending" or "query_daily": Inquiring about store ledger, total pending receivables, or daily summary (e.g., "Kitna pending hai?", "Aaj ki sale kitni hui?").
  * "list_catalog" or "search_catalog": Viewing items or asking for item price (e.g., "Menu dikhao", "Chai kitne ki hai?").
  * "general_qa": Greetings, conversational questions, or non-transactional input.

- PRICING & CALCULATION RULES:
  * Extract each distinct product into the "items" array with "product_name", "quantity" (integer >= 1), and "unit_price" (float).
  * If the spoken phrase gives a combined price (e.g. "2 coffee 60 rs"), calculate the unit_price = 30.0 (so 2 * 30 = 60).
  * If the spoken phrase is single item (e.g. "Add Burger (₹100)" or "1 burger 100"), set quantity: 1, unit_price: 100.0.
  * If customer name is mentioned (e.g. "Ramesh", "Pooja"), put in "customer_name".
  * If credit/udhaar/baaki is mentioned, set "is_credit": true, else false.

Output strictly valid JSON with this schema:
{{
  "intent": "record_sale" | "add_to_catalog" | "list_catalog" | "search_catalog" | "check_payment_status" | "query_pending" | "query_daily" | "general_qa",
  "product_name": "item name if searching catalog or checking specific payment, else null",
  "customer_name": "customer name if mentioned, else null",
  "is_credit": true | false,
  "items": [
    {{
      "product_name": "item name (e.g. coffee, burger, sandwich, notebook)",
      "quantity": 1,
      "unit_price": 50.0,
      "category": "optional category",
      "unit": "optional unit"
    }}
  ],
  "payment_status": "pending" | "paid" | "partial",
  "explanation": "Brief, polite reply in natural Hindi/Hinglish summarizing the action."
}}
"""


def build_query_prompt(query: str, context_data: dict) -> str:
    return f"""
You are VoiceLedger AI. Answer the merchant query accurately using ONLY the live facts below:
Store Financial Facts:
{json.dumps(context_data, indent=2, default=str)}

Merchant Query: "{query}"
Reply in 1-2 polite sentences of natural Hindi/Hinglish.
"""


def build_speech_refinement_prompt(text: str, lang: str = "hi") -> str:
    return f"""
Convert this shopkeeper message into punchy, natural spoken {'Hindi' if lang.startswith('hi') else 'English'} for a voice soundbox.
Keep it under 2 sentences, remove markdown/symbols, convert Rs/₹ to "rupaye".
Return ONLY the spoken text:
"{text}"
"""
