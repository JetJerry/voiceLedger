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
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10
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
        Extracts customer, items, quantities, and intent from English/Hinglish speech or text.
        Uses Gemini API if available, with a robust rule-based fallback parser.
        """
        text_clean = text.strip()
        if not text_clean:
            return VoiceExtractionResult(
                intent="unknown",
                raw_text=text,
                explanation="Koi aawaz ya text nahi mila. Kripya dobara bolein."
            )

        # 1. If Gemini API key is available, use Gemini model for extraction
        if self.client:
            try:
                catalog_prompt = f"Known menu items: {', '.join(catalog_items)}" if catalog_items else ""
                prompt = f"""
You are VoiceLedger AI, a financial voice assistant for Indian small merchants.
Analyze the following merchant speech in English or Hinglish:
"{text_clean}"

{catalog_prompt}

Extract the structured transaction and output ONLY valid JSON matching this schema:
{{
  "intent": "record_sale" | "query_pending" | "query_status" | "query_daily" | "trigger_recovery" | "general_qa",
  "customer_name": "string or null",
  "customer_phone": "string or null",
  "items": [
    {{
      "product_name": "string (lowercase item name, e.g. burger, pizza, chai)",
      "quantity": int (default 1),
      "unit_price": float or null (only if explicitly spoken)
    }}
  ],
  "payment_status": "pending" | "paid" | "partial",
  "explanation": "Short friendly reply to the merchant in natural Hinglish explaining what you understood."
}}
"""
                response = self.client.models.generate_content(
                    model=settings.LLM_MODEL,
                    contents=prompt,
                )
                response_text = response.text.strip()
                # Clean code blocks if present
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                
                parsed_json = json.loads(response_text.strip())
                items = [
                    VoiceItemExtracted(
                        product_name=it.get("product_name", "").lower(),
                        quantity=int(it.get("quantity", 1)),
                        unit_price=float(it.get("unit_price")) if it.get("unit_price") is not None else None
                    )
                    for it in parsed_json.get("items", [])
                ]
                return VoiceExtractionResult(
                    intent=parsed_json.get("intent", "record_sale"),
                    customer_name=parsed_json.get("customer_name"),
                    customer_phone=parsed_json.get("customer_phone"),
                    items=items,
                    payment_status=parsed_json.get("payment_status", "pending"),
                    raw_text=text_clean,
                    explanation=parsed_json.get("explanation")
                )
            except Exception as e:
                print(f"Gemini extraction fallback to heuristic parser due to: {e}")

        # 2. Heuristic Rule-Based / NLP Fallback Parser (Robust against Hinglish patterns)
        return self._heuristic_parse(text_clean, catalog_items or [])

    def _heuristic_parse(self, text: str, catalog_items: List[str]) -> VoiceExtractionResult:
        lower_text = text.lower()
        
        # Check intents
        if any(k in lower_text for k in ["pending", "baaki", "baki", "lena hai", "kitna paisa", "outstanding", "udhaar", "udhar"]):
            if any(k in lower_text for k in ["aaj", "today", "total", "sabka", "summary"]):
                return VoiceExtractionResult(
                    intent="query_pending",
                    raw_text=text,
                    explanation="Aaj ka total pending amount check kiya ja raha hai."
                )
        if any(k in lower_text for k in ["aaj ka sale", "today sales", "kitna collect", "daily summary", "aaj kitna hua"]):
            return VoiceExtractionResult(
                intent="query_daily",
                raw_text=text,
                explanation="Aaj ki sales aur collection summary taiyaar ki ja rahi hai."
            )
        if any(k in lower_text for k in ["reminder bhej", "resend", "dobara bhej", "recover", "vasooli", "link bhej"]):
            # Extract customer name if present
            customer_match = re.search(r"([A-Z][a-z]+|[a-z]+)\s+(ko|ka|se)", text, re.IGNORECASE)
            customer = customer_match.group(1).capitalize() if customer_match else None
            return VoiceExtractionResult(
                intent="trigger_recovery",
                customer_name=customer,
                raw_text=text,
                explanation=f"{customer or 'Customer'} ko payment recovery link bheja ja raha hai."
            )
        if any(k in lower_text for k in ["payment aaya", "pay kiya", "status kya", "aaya kya", "verify"]):
            customer_match = re.search(r"([A-Z][a-z]+|[a-z]+)\s+(ka|ne|se)", text, re.IGNORECASE)
            customer = customer_match.group(1).capitalize() if customer_match else None
            return VoiceExtractionResult(
                intent="query_status",
                customer_name=customer,
                raw_text=text,
                explanation=f"{customer or 'Customer'} ka payment status verify kiya ja raha hai."
            )

        # Default: Record Sale Intent
        # Extract Customer: "Rahul ko", "Rahul se", "Customer Rahul", "To Rahul"
        customer = None
        cust_patterns = [
            r"([A-Za-z]+)\s+(?:ko|se|ne|k)",
            r"(?:for|to|customer)\s+([A-Za-z]+)",
            r"^([A-Za-z]+)\s+(?:\d+|do|ek|teen|two|one)",
        ]
        for pat in cust_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                cand = m.group(1).strip()
                if cand.lower() not in ["aaj", "ek", "do", "teen", "char", "two", "one", "burger", "pizza", "coke", "chai"]:
                    customer = cand.capitalize()
                    break

        # Extract items and quantities
        items: List[VoiceItemExtracted] = []
        known_products = [c.lower() for c in catalog_items] if catalog_items else [
            "burger", "cheese burger", "pizza", "veg pizza", "coke", "cold drink", "tea", "chai", "coffee", "veg thali", "paneer roll", "samosa", "sandwich"
        ]

        # Search for product mentions
        for prod in sorted(known_products, key=len, reverse=True):
            if prod in lower_text:
                # Look for quantity before product: "2 burger", "do burger", "two burger"
                qty = 1
                pattern = rf"(\d+|ek|do|teen|char|chaar|paanch|one|two|three|four|five)\s+{re.escape(prod)}"
                qm = re.search(pattern, lower_text)
                if qm:
                    qty_word = qm.group(1).lower()
                    qty = HINDI_NUMBERS.get(qty_word, 1)

                # Check if unit price mentioned e.g. "100 each", "100 rupaye", "100 rs"
                price_match = re.search(rf"{re.escape(prod)}.*?(\d+)\s*(?:each|rupaye|rs|inr|per)", lower_text)
                unit_price = float(price_match.group(1)) if price_match else None

                items.append(VoiceItemExtracted(
                    product_name=prod,
                    quantity=qty,
                    unit_price=unit_price
                ))

        # If no known products found, look for generic pattern e.g. "500 rupaye" or "2 items"
        if not items:
            amount_match = re.search(r"(\d+)\s*(?:rupaye|rs|inr|rupya)", lower_text)
            if amount_match:
                items.append(VoiceItemExtracted(
                    product_name="general item",
                    quantity=1,
                    unit_price=float(amount_match.group(1))
                ))
            else:
                items.append(VoiceItemExtracted(
                    product_name="burger",
                    quantity=1
                ))

        explanation = f"{customer or 'Customer'} ke liye {', '.join([f'{i.quantity}x {i.product_name}' for i in items])} ka sale record kiya gaya."
        return VoiceExtractionResult(
            intent="record_sale",
            customer_name=customer or "Walk-in Customer",
            items=items,
            payment_status="pending",
            raw_text=text,
            explanation=explanation
        )

    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        """
        Answers a merchant natural-language question using provided financial facts.
        """
        if self.client:
            try:
                prompt = f"""
You are VoiceLedger, an AI revenue recovery and financial assistant for a merchant.
Answer the merchant's question concisely in polite, natural Hinglish.

Context Data:
{json.dumps(context_data, indent=2, default=str)}

Merchant Question:
"{query}"

Respond in 1-2 friendly sentences. Always state exact amounts and customer names accurately from the context.
"""
                response = self.client.models.generate_content(
                    model=settings.LLM_MODEL,
                    contents=prompt
                )
                return response.text.strip()
            except Exception as e:
                print(f"Gemini answer fallback due to: {e}")

        # Rule-based response formatting
        if "pending" in query.lower() or "baaki" in query.lower():
            pending_amt = context_data.get("total_outstanding", 0.0)
            pending_count = context_data.get("pending_count", 0) + context_data.get("partial_count", 0)
            return f"Aapka kul ₹{pending_amt:,.2f} pending hai across {pending_count} sales."
        
        if "sale" in query.lower() or "today" in query.lower() or "aaj" in query.lower():
            today_sales = context_data.get("today_sales", 0.0)
            collected = context_data.get("total_collected", 0.0)
            return f"Aaj ka total sale ₹{today_sales:,.2f} hai, jisme se ₹{collected:,.2f} collect ho chuka hai."
            
        return f"Aapka request process kar diya gaya hai. Outstanding amount: ₹{context_data.get('total_outstanding', 0.0):,.2f}."


llm_service = LLMService()
