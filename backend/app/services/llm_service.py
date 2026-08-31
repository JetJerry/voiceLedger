import json
import logging
import re
from typing import Any, Dict, List, Optional

from backend.app.config import settings
from backend.app.schemas.voice import VoiceExtractionResult, VoiceItemExtracted

logger = logging.getLogger("voiceledger.llm")

HINDI_NUMBERS = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
    "che": 6, "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    "एक": 1, "वन": 1, "१": 1,
    "दो": 2, "तू": 2, "टू": 2, "२": 2,
    "तीन": 3, "थ्री": 3, "३": 3,
    "चार": 4, "फोर": 4, "४": 4,
    "पांच": 5, "पाँच": 5, "फाइव": 5, "५": 5,
    "छह": 6, "छः": 6, "सिक्स": 6, "६": 6,
    "सात": 7, "सेवन": 7, "७": 7,
    "आठ": 8, "एट": 8, "८": 8,
    "नौ": 9, "नाइन": 9, "९": 9,
    "दस": 10, "टेन": 10, "१०": 10,
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
    "शर्ट": "shirt",
}


class BaseLLMProvider:
    name = "base"

    def extract_transaction(self, text: str, catalog_items: Optional[List[str]] = None) -> VoiceExtractionResult:
        raise NotImplementedError

    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        raise NotImplementedError

    @staticmethod
    def _strip_markdown_json(raw_text: str) -> str:
        text = raw_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _parse_items(self, data: Dict[str, Any]) -> List[VoiceItemExtracted]:
        items: List[VoiceItemExtracted] = []
        for raw_item in data.get("items", []):
            if not raw_item.get("product_name"):
                continue
            items.append(
                VoiceItemExtracted(
                    product_name=str(raw_item.get("product_name", "")).strip().lower(),
                    quantity=int(raw_item.get("quantity", 1) or 1),
                    unit_price=float(raw_item.get("unit_price")) if raw_item.get("unit_price") is not None else None,
                    category=str(raw_item.get("category", "")).strip() if raw_item.get("category") else None,
                )
            )
        return items


class GeminiLLMProvider(BaseLLMProvider):
    name = "gemini"

    def __init__(self):
        self.client = None
        if settings.GEMINI_API_KEY:
            try:
                from google import genai

                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as exc:
                logger.warning("Could not initialize Gemini client: %s", exc)

    def extract_transaction(self, text: str, catalog_items: Optional[List[str]] = None) -> VoiceExtractionResult:
        if not self.client:
            raise RuntimeError("Gemini client not configured")

        catalog_prompt = f"Merchant product catalog: {', '.join(catalog_items)}" if catalog_items else ""
        prompt = f"""
You are VoiceLedger AI, a financial voice assistant for merchants.
Analyze what the merchant spoke in Hindi, Hinglish, or English:
"{text}"

{catalog_prompt}

Identify the intent and extract items/prices. The merchant can:
- Record a sale (selling items to customers)
- Add new items to their catalog/menu (e.g. "menu mein add karo", "naya item daalo", "add item")
- Check payment status
- Query pending amounts or daily summary

Output ONLY valid JSON:
{{
  "intent": "record_sale" | "add_to_catalog" | "check_payment_status" | "query_pending" | "query_daily" | "general_qa",
  "product_name": "optional product name if checking status for a specific item, else null",
  "items": [
    {{
      "product_name": "item name in standard english (e.g. coffee, dal makhani, hammer, notebook)",
      "quantity": int (default 1),
      "unit_price": float or null (if spoken or inferred from total),
      "category": "optional category (e.g. Snacks, Beverages, Meals, Stationery, Hardware, General)"
    }}
  ],
  "payment_status": "pending" | "paid" | "partial",
  "explanation": "Short friendly reply in natural Hindi/English explaining what you understood."
}}
"""
        try:
            response = self.client.models.generate_content(model=settings.LLM_MODEL, contents=prompt)
            response_text = self._strip_markdown_json(response.text)
            data = json.loads(response_text)
            return VoiceExtractionResult(
                intent=data.get("intent", "record_sale"),
                product_name=data.get("product_name"),
                items=self._parse_items(data),
                payment_status=data.get("payment_status", "pending"),
                raw_text=text,
                explanation=data.get("explanation"),
            )
        except Exception as exc:
            logger.warning("Gemini extraction failed: %s", exc)
            raise

    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        if not self.client:
            raise RuntimeError("Gemini client not configured")

        prompt = f"""
You are VoiceLedger AI. Answer the merchant's query accurately in natural Hindi/Hinglish.

Live Database Facts:
{json.dumps(context_data, indent=2, default=str)}

Merchant Query:
"{query}"

Answer directly in 1-2 friendly sentences.
"""
        try:
            response = self.client.models.generate_content(model=settings.LLM_MODEL, contents=prompt)
            return response.text.strip()
        except Exception as exc:
            logger.warning("Gemini answer generation failed: %s", exc)
            raise


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def __init__(self):
        self.client = None
        if settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI

                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            except Exception as exc:
                logger.warning("Could not initialize OpenAI client: %s", exc)

    def extract_transaction(self, text: str, catalog_items: Optional[List[str]] = None) -> VoiceExtractionResult:
        if not self.client:
            raise RuntimeError("OpenAI client not configured")

        catalog_prompt = f"Merchant product catalog: {', '.join(catalog_items)}" if catalog_items else ""
        prompt = f"""
You are VoiceLedger AI, a financial voice assistant for merchants.
Analyze what the merchant spoke in Hindi, Hinglish, or English:
"{text}"

{catalog_prompt}

Identify the intent and extract items/prices. The merchant can:
- Record a sale (selling items to customers)
- Add new items to their catalog/menu (e.g. "menu mein add karo", "naya item daalo", "add item")
- Check payment status
- Query pending amounts or daily summary

Output ONLY valid JSON with keys:
{{
  "intent": "record_sale" | "add_to_catalog" | "check_payment_status" | "query_pending" | "query_daily" | "general_qa",
  "product_name": "optional product name if checking status or adding an item, else null",
  "items": [
    {{
      "product_name": "item name in standard english",
      "quantity": int (default 1),
      "unit_price": float or null,
      "category": "optional category name"
    }}
  ],
  "payment_status": "pending" | "paid" | "partial",
  "explanation": "Short friendly reply in natural Hindi/English."
}}
"""
        try:
            response = self.client.responses.create(
                model=settings.LLM_MODEL,
                input=prompt,
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
            response_text = self._strip_markdown_json(response.output_text or "")
            data = json.loads(response_text)
            return VoiceExtractionResult(
                intent=data.get("intent", "record_sale"),
                product_name=data.get("product_name"),
                items=self._parse_items(data),
                payment_status=data.get("payment_status", "pending"),
                raw_text=text,
                explanation=data.get("explanation"),
            )
        except Exception as exc:
            logger.warning("OpenAI extraction failed: %s", exc)
            raise

    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        if not self.client:
            raise RuntimeError("OpenAI client not configured")

        prompt = f"Answer the merchant query in Hindi/Hinglish. Data: {json.dumps(context_data, default=str)} Query: {query}"
        try:
            response = self.client.responses.create(
                model=settings.LLM_MODEL,
                input=prompt,
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
            return (response.output_text or "").strip()
        except Exception as exc:
            logger.warning("OpenAI answer generation failed: %s", exc)
            raise


class MockLLMProvider(BaseLLMProvider):
    name = "mock"

    def __init__(self):
        self.client = None

    def extract_transaction(self, text: str, catalog_items: Optional[List[str]] = None) -> VoiceExtractionResult:
        return VoiceExtractionResult(
            intent="record_sale",
            raw_text=text,
            items=[],
            payment_status="pending",
            explanation="Demo mode active. Please configure a real LLM provider for production extraction.",
        )

    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        return "Demo mode active. Configure Gemini or OpenAI to enable live merchant responses."


class LLMService:
    def __init__(self):
        self.gemini_api_key = settings.GEMINI_API_KEY
        self.client = None
        provider_name = (settings.LLM_PROVIDER or "gemini").lower()

        if provider_name == "gemini":
            self.provider = GeminiLLMProvider()
        elif provider_name == "openai":
            self.provider = OpenAIProvider()
        else:
            self.provider = MockLLMProvider()

        self.client = getattr(self.provider, "client", None)

    def extract_transaction(self, text: str, catalog_items: Optional[List[str]] = None) -> VoiceExtractionResult:
        text_clean = text.strip()
        if not text_clean:
            return VoiceExtractionResult(
                intent="unknown",
                raw_text=text,
                explanation="Koi aawaz ya text nahi mila. Kripya dobara bolein.",
            )

        try:
            return self.provider.extract_transaction(text_clean, catalog_items)
        except Exception as exc:
            logger.warning("Provider extraction failed for %s: %s", settings.LLM_PROVIDER, exc)
            return self._dynamic_parse(text_clean, catalog_items or [])

    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        try:
            return self.provider.answer_query(query, context_data)
        except Exception as exc:
            logger.warning("Provider answer failed for %s: %s", settings.LLM_PROVIDER, exc)
            return self._answer_from_context(query, context_data)

    def _dynamic_parse(self, text: str, catalog_items: List[str]) -> VoiceExtractionResult:
        lower_text = text.lower()

        # Intent: Check payment arrival
        payment_check_keywords = [
            "payment aaya", "paisa aaya", "pay hua", "check payment",
            "payment status", "status kya hai", "aaya ya nahi", "did payment arrive", "received or not",
            "verify payment", "payment mila", "paisa mila",
            "पेमेंट आया", "पैसा आया", "पेमेंट मिला", "पैसा मिला", "स्टेटस क्या है", "पेमेंट चेक",
        ]
        if any(k in lower_text for k in payment_check_keywords):
            matched_prod = None
            for prod in catalog_items:
                if prod.lower() in lower_text:
                    matched_prod = prod.lower()
                    break
            for dev_k, eng_v in DEVANAGARI_PRODUCT_MAP.items():
                if dev_k in text:
                    matched_prod = eng_v
                    break
            return VoiceExtractionResult(
                intent="check_payment_status",
                product_name=matched_prod,
                raw_text=text,
                explanation=f"{matched_prod or 'Sold item'} ka payment status check kiya ja raha hai...",
            )

        # Intent: Add new item to catalog/menu via voice
        is_catalog_add = (
            (any(w in lower_text for w in ["add", "daalo", "dalo", "jodo", "जोड़ो", "ऐड", "list"]))
            and (any(w in lower_text for w in ["menu", "catalog", "item", "product", "saman", "मेन्यू", "आइटम", "समान", "सामान"]))
        ) or any(k in lower_text for k in [
            "add item", "add product", "add to menu", "menu me add", "menu mein add",
            "catalog me add", "catalog mein add", "naya item", "naya product", "naya saman",
            "item add karo", "item add karna", "product add", "new item", "add in menu",
            "menu me dalo", "menu mein dalo", "list karo", "catalog me daalo",
            "मेन्यू में ऐड", "मेन्यू में जोड़ो", "आइटम जोड़ो", "नया आइटम", "ऐड करो", "जोड़ो",
        ])

        if is_catalog_add:
            # Extract price if present
            price_found = 0.0
            price_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:each|per|rupaye|rs|rupya|inr|/-|रुपये|रुपया|रु)", lower_text)
            if price_match:
                price_found = float(price_match.group(1))
            else:
                num_match = re.search(r"\b(\d+)\b", lower_text)
                if num_match:
                    price_found = float(num_match.group(1))

            # Clean item name by stripping command words
            cleaned = lower_text
            for trigger in [
                "menu mein add karo", "menu me add karo", "catalog mein add karo", "catalog me add karo",
                "menu mein", "menu me", "menu", "catalog mein", "catalog me", "catalog",
                "add to menu", "add in menu", "add item", "add product", "naya item", "naya product", "naya saman",
                "item add karo", "item add", "product add", "add karo", "add", "daalo", "dalo", "jodo", "karo", "please",
                "rupaye", "rs", "inr", "rupya", "price", "rate", "ka", "ki", "ke", "hai", "me", "mein",
                "मेन्यू में जोड़ो", "मेन्यू में ऐड करो", "मेन्यू में", "मेन्यू", "आइटम जोड़ो", "नया आइटम", "ऐड करो", "जोड़ो", "रुपये", "रुपया",
            ]:
                cleaned = re.sub(rf"\b{re.escape(trigger)}\b", " ", cleaned)
            cleaned = re.sub(r"\d+", " ", cleaned).strip()
            item_name = " ".join(cleaned.split()[:4]) if cleaned else "New Product"

            # Check devanagari product map
            for dev_k, eng_v in DEVANAGARI_PRODUCT_MAP.items():
                if dev_k in text:
                    item_name = eng_v
                    break

            return VoiceExtractionResult(
                intent="add_to_catalog",
                product_name=item_name,
                items=[VoiceItemExtracted(product_name=item_name, unit_price=price_found, category="General")],
                raw_text=text,
                explanation=f"'{item_name.title()}' (Rs. {price_found:.2f}) ko catalog me add kiya ja raha hai.",
            )

        if any(k in lower_text for k in ["pending", "baaki", "baki", "lena hai", "outstanding", "udhaar", "बाकी", "पेंडिंग"]):
            return VoiceExtractionResult(
                intent="query_pending",
                raw_text=text,
                explanation="Total pending payments check kiye ja rahe hain.",
            )

        if any(k in lower_text for k in ["aaj ka sale", "today sales", "kitna collect", "daily summary", "aaj kitna hua", "आज का सेल"]):
            return VoiceExtractionResult(
                intent="query_daily",
                raw_text=text,
                explanation="Aaj ki sales aur collection summary check ki ja rahi hai.",
            )

        items: List[VoiceItemExtracted] = []
        price_found = None
        price_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:each|per|rupaye|rs|rupya|inr|/-|रुपये|रुपया|रु)", lower_text)
        if price_match:
            price_found = float(price_match.group(1))

        found_devanagari = False
        for dev_word, eng_name in sorted(DEVANAGARI_PRODUCT_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if dev_word in text:
                qty = 1
                pattern = rf"(\S+)\s+{re.escape(dev_word)}"
                qm = re.search(pattern, text)
                if qm:
                    word_before = qm.group(1).strip()
                    qty = HINDI_NUMBERS.get(word_before, 1)
                items.append(VoiceItemExtracted(product_name=eng_name, quantity=qty, unit_price=price_found))
                found_devanagari = True

        if not found_devanagari:
            for prod in sorted(catalog_items, key=len, reverse=True):
                if prod.lower() in lower_text:
                    qty = 1
                    qty_pattern = rf"(\S+)\s+{re.escape(prod.lower())}"
                    qm = re.search(qty_pattern, lower_text)
                    if qm:
                        qty = HINDI_NUMBERS.get(qm.group(1).lower(), 1)
                    items.append(VoiceItemExtracted(product_name=prod.lower(), quantity=qty, unit_price=price_found))

        if not items:
            qty = 1
            qty_match = re.search(r"\b(\d+|ek|do|teen|char|chaar|paanch|one|two|three|four|five|एक|दो|तीन|चार|पांच)\b", lower_text)
            if qty_match:
                qty_word = qty_match.group(1).lower()
                qty = HINDI_NUMBERS.get(qty_word, int(qty_word) if qty_word.isdigit() else 1)

            cleaned = lower_text
            for stop in [
                "diye", "diya", "sold", "becha", "pack", "karo", "please", "ka", "ki", "ke", "aur", "and",
                "rupaye", "rs", "inr", "rupya", "each", "per", "total", "order", "item", "दिए", "दिया", "रुपये",
            ]:
                cleaned = re.sub(rf"\b{stop}\b", " ", cleaned)
            cleaned = re.sub(r"\d+", " ", cleaned).strip()
            product_name = " ".join(cleaned.split()[:3]) if cleaned else "item"
            items.append(VoiceItemExtracted(product_name=product_name, quantity=qty, unit_price=price_found))

        items_str = ", ".join([f"{it.quantity}x {it.product_name}" for it in items])
        explanation = f"{items_str} ka sale record kiya gaya."

        return VoiceExtractionResult(
            intent="record_sale",
            items=items,
            payment_status="pending",
            raw_text=text,
            explanation=explanation,
        )

    def _answer_from_context(self, query: str, context_data: Dict[str, Any]) -> str:
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
