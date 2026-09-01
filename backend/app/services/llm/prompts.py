import json
from typing import Optional, List, Dict, Any


def build_extraction_prompt(
    text: str,
    catalog_items: Optional[List[str]] = None,
    merchant_profile: Optional[dict] = None,
    business_type: Optional[str] = None,
    context: str = "terminal",
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Constructs the prompt for extracting structured transactional intent, items, and pricing
    with conversational context memory.
    """
    catalog_prompt = (
        f"Merchant Store Product Catalog (Known Items): {', '.join(catalog_items)}."
        if catalog_items
        else "Merchant Store Product Catalog: Open Catalog Mode (any product spoken by the merchant can be sold or registered)."
    )
    profile_prompt = f"Merchant Profile: {json.dumps(merchant_profile, default=str)}" if merchant_profile else ""
    business_prompt = f"Business Type: {business_type}" if business_type else ""
    context_hint = (
        "Active Workspace Tab: Product Catalog & Menu Management (prioritize add_to_catalog, list_catalog, search_catalog)."
        if context == "catalog"
        else "Active Workspace Tab: Sales & Payment Terminal (prioritize record_sale, check_payment_status)."
    )

    history_prompt = ""
    if history and len(history) > 0:
        turns = []
        for turn in history[-6:]:
            role = "Merchant" if turn.get("role") in ["user", "merchant"] else "Voice Assistant"
            content = str(turn.get("content", "")).strip()
            if content:
                turns.append(f"{role}: \"{content}\"")
        if turns:
            history_prompt = "Recent Conversation History (Context Memory):\n" + "\n".join(turns) + "\n"

    return f"""
You are VoiceLedger AI, an intelligent conversational transactional voice agent for Indian shopkeepers and retail merchants.
Analyze what the merchant spoke or typed in Hindi, Hinglish, or English:
"{text}"

{catalog_prompt}
{profile_prompt}
{business_prompt}
{context_hint}
{history_prompt}

STRICT AGENT INSTRUCTIONS & CONTEXT RULES:
1. MULTI-TURN CONVERSATION MEMORY:
   - Check the Recent Conversation History:
     * If the previous turn was about adding/modifying products or menu (e.g., Merchant asked "Add products" / "Menu me item add karo" and Assistant asked "Which product and price?"), and the merchant now provides items or pricing (e.g. "Burger 100 rupaye", "2 coffee 50 rs"), classify intent as "add_to_catalog".
     * If the merchant asks a follow-up about a previously discussed item, maintain the context of that item.

2. CLASSIFY INTENT ACCURATELY:
   * "add_to_catalog": When adding or updating products/menu items in the store inventory (e.g., "Menu mein burger add karo 100 rupaye", "Add products", "Burger 100 rs" in catalog context or follow-up).
   * "list_catalog": When the merchant asks to view, list, or check available products/menu (e.g., "Menu dikhao", "Catalog list karo", "Kya kya items hain?", "Show my products", "Catalog batao kitne items hain").
   * "search_catalog": When the merchant asks for a specific product's price or availability (e.g., "Coffee ka price kya hai?", "Chai kitne ki hai?", "Samosa hai kya?"). Put the item name in "product_name".
   * "record_sale": When the merchant records a customer sale or transaction in the terminal (e.g., "2 coffee 60 rs", "3 notebook 150 rs", "Ramesh ka 2 chai 20 rs baaki").
   * "check_payment_status": When inquiring if payment arrived for a customer or item (e.g., "Payment aaya kya?", "Burger ka payment hua?").
   * "query_pending" or "query_daily": Inquiring about outstanding customer debt or daily sales totals (e.g., "Kitna pending hai?", "Aaj ki sale kitni hui?").
   * "general_qa": Greetings or general queries.

3. PRICING & ITEM EXTRACTION:
   * Extract items into the "items" array with "product_name", "quantity" (integer >= 1), "unit_price" (float), and optional "category" / "unit".
   * If combined price is given (e.g. "2 coffee 60 rs"), unit_price = 30.0.
   * If single item (e.g. "Burger 100 rs"), quantity = 1, unit_price = 100.0.
   * If customer name is mentioned (e.g. "Ramesh", "Pooja"), extract into "customer_name".
   * If credit/udhaar/baaki is mentioned, set "is_credit": true, else false.

Output strictly valid JSON with this schema:
{{
  "intent": "record_sale" | "add_to_catalog" | "list_catalog" | "search_catalog" | "check_payment_status" | "query_pending" | "query_daily" | "general_qa",
  "product_name": "item name if searching catalog or checking specific payment, else null",
  "customer_name": "customer name if mentioned, else null",
  "is_credit": true | false,
  "items": [
    {{
      "product_name": "item name",
      "quantity": 1,
      "unit_price": 50.0,
      "category": "optional category",
      "unit": "optional unit"
    }}
  ],
  "payment_status": "pending" | "paid" | "partial",
  "explanation": "Polite reply in natural Hindi/Hinglish summarizing the exact action."
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
