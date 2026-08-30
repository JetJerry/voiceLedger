import json
import re
from typing import Dict, Any, Optional, List
from backend.app.config import settings
from backend.app.schemas.voice import VoiceExtractionResult, VoiceItemExtracted


HINDI_NUMBERS = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
    "che": 6, "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    # Devanagari numerals and phonetics
    "एक": 1, "वन": 1, "१": 1,
    "दो": 2, "तू": 2, "टू": 2, "२": 2,
    "तीन": 3, "थ्री": 3, "३": 3,
    "चार": 4, "फोर": 4, "४": 4,
    "पांच": 5, "पाँच": 5, "फाइव": 5, "५": 5,
    "छह": 6, "छः": 6, "सिक्स": 6, "६": 6,
    "सात": 7, "सेवन": 7, "७": 7,
    "आठ": 8, "एट": 8, "८": 8,
    "नौ": 9, "नाइन": 9, "९": 9,
    "दस": 10, "टेन": 10, "१०": 10
}

DEVANAGARI_PRODUCT_MAP = {
    "कॉफी": "coffee", "काफी": "coffee", "कौफी": "coffee", "कोफ़ी": "coffee",
    "चाय": "tea", "टी": "tea",
    "बर्गर": "burger",
    "पिज़्ज़ा": "pizza", "पिज़ा": "pizza", "पिज़्ज़ा": "pizza",
    "समोसा": "samosa", "समोसे": "samosa",
    "सैंडविच": "sandwich", "सैंडविज": "sandwich",
    "कोक": "coke", "कोल्डड्रिंक": "coke",
    "नोटबुक": "notebook", "कापी": "notebook", "कॉपी": "notebook",
    "पेन": "pen", "कलम": "pen",
    "शर्ट": "shirt"
}


class LLMService:
    def __init__(self):
        self.gemini_api_key = settings.GEMINI_API_KEY
        self.client = None
        if self.gemini_api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.gemini_api_key)
            except Exception as e:
                print(f"Warning: Could not initialize Gemini client: {e}")

    def extract_transaction(self, text: str, catalog_items: Optional[List[str]] = None) -> VoiceExtractionResult:
        """
        Extracts sold products, quantities, prices, or payment verification queries dynamically.
        Supports both Hindi Devanagari script and Latin Hinglish/English script.
        """
        text_clean = text.strip()
        if not text_clean:
            return VoiceExtractionResult(
                intent="unknown",
                raw_text=text,
                explanation="Koi aawaz ya text nahi mila. Kripya dobara bolein."
            )

        # 1. Gemini LLM Structured Extraction (if API key available)
        if self.client:
            try:
                catalog_prompt = f"Merchant product catalog: {', '.join(catalog_items)}" if catalog_items else ""
                prompt = f"""
You are VoiceLedger AI, a financial voice assistant for merchants.
Analyze what the merchant spoke in Hindi, Hinglish, or English:
"{text_clean}"

{catalog_prompt}

Identify the intent and extract sold items and prices. Output ONLY valid JSON:
{{
  "intent": "record_sale" | "check_payment_status" | "query_pending" | "query_daily" | "general_qa",
  "product_name": "optional product name if checking status for a specific item, else null",
  "items": [
    {{
      "product_name": "item name in standard english (e.g. coffee, burger, pizza, tea)",
      "quantity": int (default 1),
      "unit_price": float or null (if spoken or inferred from total)
    }}
  ],
  "payment_status": "pending" | "paid" | "partial",
  "explanation": "Short friendly reply in natural Hindi/English explaining what you understood."
}}
"""
                response = self.client.models.generate_content(
                    model=settings.LLM_MODEL,
                    contents=prompt,
                )
                response_text = response.text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]

                parsed_json = json.loads(response_text.strip())
                items = [
                    VoiceItemExtracted(
                        product_name=it.get("product_name", "").strip().lower(),
                        quantity=int(it.get("quantity", 1)),
                        unit_price=float(it.get("unit_price")) if it.get("unit_price") is not None else None
                    )
                    for it in parsed_json.get("items", [])
                    if it.get("product_name")
                ]
                return VoiceExtractionResult(
                    intent=parsed_json.get("intent", "record_sale"),
                    product_name=parsed_json.get("product_name"),
                    items=items,
                    payment_status=parsed_json.get("payment_status", "pending"),
                    raw_text=text_clean,
                    explanation=parsed_json.get("explanation")
                )
            except Exception as e:
                print(f"Gemini dynamic extraction fallback to parser: {e}")

        # 2. Dynamic Rule-Based / Speech Parser (Hindi & Hinglish)
        return self._dynamic_parse(text_clean, catalog_items or [])

    def _dynamic_parse(self, text: str, catalog_items: List[str]) -> VoiceExtractionResult:
        lower_text = text.lower()

        # Intent: Check payment arrival (Hinglish + Devanagari)
        payment_check_keywords = [
            "payment aaya", "paisa aaya", "pay hua", "check payment",
            "payment status", "status kya hai", "aaya ya nahi", "did payment arrive", "received or not",
            "verify payment", "payment mila", "paisa mila",
            "पेमेंट आया", "पैसा आया", "पेमेंट मिला", "पैसा मिला", "स्टेटस क्या है", "पेमेंट चेक"
        ]
        if any(k in lower_text for k in payment_check_keywords):
            matched_prod = None
            for prod in catalog_items:
                if prod.lower() in lower_text:
                    matched_prod = prod.lower()
                    break
            # Check devanagari product names
            for dev_k, eng_v in DEVANAGARI_PRODUCT_MAP.items():
                if dev_k in text:
                    matched_prod = eng_v
                    break

            return VoiceExtractionResult(
                intent="check_payment_status",
                product_name=matched_prod,
                raw_text=text,
                explanation=f"{matched_prod or 'Sold item'} ka payment status check kiya ja raha hai..."
            )

        # Intent: Pending Query
        if any(k in lower_text for k in ["pending", "baaki", "baki", "lena hai", "outstanding", "udhaar", "बाकी", "पेंडिंग"]):
            return VoiceExtractionResult(
                intent="query_pending",
                raw_text=text,
                explanation="Total pending payments check kiye ja rahe hain."
            )

        # Intent: Daily Summary Query
        if any(k in lower_text for k in ["aaj ka sale", "today sales", "kitna collect", "daily summary", "aaj kitna hua", "आज का सेल"]):
            return VoiceExtractionResult(
                intent="query_daily",
                raw_text=text,
                explanation="Aaj ki sales aur collection summary check ki ja rahi hai."
            )

        # Intent: Record Product Sale (Hindi Devanagari + Latin Hinglish)
        items: List[VoiceItemExtracted] = []

        # Extract explicit unit price or total price from speech if spoken
        price_found = None
        price_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:each|per|rupaye|rs|rupya|inr|/-|रुपये|रुपया|रु)", lower_text)
        if price_match:
            price_found = float(price_match.group(1))

        # 1. Match Devanagari Hindi Products & Numerals (e.g. "तू काफी वन बर्गर", "दो कॉफी और एक समोसा")
        found_devanagari = False
        for dev_word, eng_name in sorted(DEVANAGARI_PRODUCT_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if dev_word in text:
                qty = 1
                # Find number preceding this item
                pattern = rf"(\S+)\s+{re.escape(dev_word)}"
                qm = re.search(pattern, text)
                if qm:
                    word_before = qm.group(1).strip()
                    qty = HINDI_NUMBERS.get(word_before, 1)
                
                items.append(VoiceItemExtracted(
                    product_name=eng_name,
                    quantity=qty,
                    unit_price=price_found
                ))
                found_devanagari = True

        # 2. Match Catalog items
        if not found_devanagari:
            for prod in sorted(catalog_items, key=len, reverse=True):
                if prod.lower() in lower_text:
                    qty = 1
                    qty_pattern = rf"(\S+)\s+{re.escape(prod.lower())}"
                    qm = re.search(qty_pattern, lower_text)
                    if qm:
                        qty = HINDI_NUMBERS.get(qm.group(1).lower(), 1)
                    
                    items.append(VoiceItemExtracted(
                        product_name=prod.lower(),
                        quantity=qty,
                        unit_price=price_found
                    ))

        # 3. Dynamic Fallback extraction if no predefined words matched
        if not items:
            qty = 1
            qty_match = re.search(r"\b(\d+|ek|do|teen|char|chaar|paanch|one|two|three|four|five|एक|दो|तीन|चार|पांच)\b", lower_text)
            if qty_match:
                qty_word = qty_match.group(1).lower()
                qty = HINDI_NUMBERS.get(qty_word, int(qty_word) if qty_word.isdigit() else 1)

            cleaned = lower_text
            for stop in [
                "diye", "diya", "sold", "becha", "pack", "karo", "please", "ka", "ki", "ke", "aur", "and",
                "rupaye", "rs", "inr", "rupya", "each", "per", "total", "order", "item", "दिए", "दिया", "रुपये"
            ]:
                cleaned = re.sub(rf"\b{stop}\b", " ", cleaned)
            cleaned = re.sub(r"\d+", " ", cleaned).strip()
            product_name = " ".join(cleaned.split()[:3]) if cleaned else "item"

            items.append(VoiceItemExtracted(
                product_name=product_name,
                quantity=qty,
                unit_price=price_found
            ))

        items_str = ", ".join([f"{it.quantity}x {it.product_name}" for it in items])
        explanation = f"{items_str} ka sale record kiya gaya."

        return VoiceExtractionResult(
            intent="record_sale",
            items=items,
            payment_status="pending",
            raw_text=text,
            explanation=explanation
        )

    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        if self.client:
            try:
                prompt = f"""
You are VoiceLedger AI. Answer the merchant's query accurately in natural Hindi/Hinglish.

Live Database Facts:
{json.dumps(context_data, indent=2, default=str)}

Merchant Query:
"{query}"

Answer directly in 1-2 friendly sentences.
"""
                response = self.client.models.generate_content(
                    model=settings.LLM_MODEL,
                    contents=prompt
                )
                return response.text.strip()
            except Exception as e:
                print(f"Gemini answer fallback: {e}")

        if "pending" in query.lower() or "baaki" in query.lower() or "बाकी" in query:
            pending_amt = context_data.get("total_outstanding", 0.0)
            pending_count = context_data.get("pending_count", 0) + context_data.get("partial_count", 0)
            return f"Aapka kul Rs. {pending_amt:,.2f} pending hai ({pending_count} sales)."

        if "sale" in query.lower() or "today" in query.lower() or "aaj" in query.lower() or "आज" in query:
            today_sales = context_data.get("today_sales", 0.0)
            collected = context_data.get("total_collected", 0.0)
            return f"Aaj ka total sale Rs. {today_sales:,.2f} hai, jisme se Rs. {collected:,.2f} collect ho chuka hai."

        return f"Outstanding amount: Rs. {context_data.get('total_outstanding', 0.0):,.2f}."


llm_service = LLMService()
