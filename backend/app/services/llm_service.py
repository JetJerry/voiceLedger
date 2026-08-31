import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

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
    "चाय": "tea", "टी": "tea", "chai": "chai",
    "बर्गर": "burger",
    "पिज़्ज़ा": "pizza", "पिज़ा": "pizza", "पिज़्ज़ा": "pizza",
    "समोसा": "samosa", "समोसे": "samosa",
    "सैंडविच": "sandwich", "सैंडविज": "sandwich",
    "कोक": "coke", "कोल्डड्रिंक": "cold drink",
    "आटा": "atta", "atta": "atta",
    "तेल": "mustard oil", "सरसों का तेल": "mustard oil",
    "चीनी": "sugar", "शक्कर": "sugar",
    "दूध": "milk", "doodh": "milk",
    "पनीर": "paneer",
    "नोटबुक": "notebook", "कापी": "notebook", "कॉपी": "notebook",
    "पेन": "ball pen", "कलम": "ball pen",
    "शर्ट": "shirt",
    "कुर्ता": "kurta",
    "दाल मखनी": "dal makhani",
    "बटर चिकन": "butter chicken",
}


def _build_extraction_prompt(
    text: str,
    catalog_items: Optional[List[str]] = None,
    merchant_profile: Optional[dict] = None,
    business_type: Optional[str] = None,
    context: str = "terminal",
) -> str:
    catalog_prompt = (
        f"Merchant Store Product Catalog (ONLY use these exact names for sales): {', '.join(catalog_items)}"
        if catalog_items
        else "Merchant Store Product Catalog: EMPTY — no products yet. Do NOT invent products for record_sale."
    )
    profile_prompt = f"Merchant Profile: {json.dumps(merchant_profile, default=str)}" if merchant_profile else ""
    business_prompt = f"Business Type: {business_type}" if business_type else ""
    context_hint = (
        "Context: catalog/menu management tab — prioritize add_to_catalog, list_catalog, search_catalog intents."
        if context == "catalog"
        else "Context: voice terminal for sales and payments."
    )

    return f"""
You are VoiceLedger AI, an intelligent financial voice assistant for Indian retail shopkeepers.
Analyze what the merchant spoke in Hindi, Hinglish, or English:
"{text}"

{catalog_prompt}
{profile_prompt}
{business_prompt}
{context_hint}

STRICT RULES (anti-hallucination):
- For "record_sale": ONLY include items that exist in the catalog list above OR were explicitly named with a spoken price.
- NEVER invent product names, quantities, or prices not mentioned in speech.
- For financial queries (pending, daily sales): set intent to query_pending or query_daily — do NOT make up numbers in explanation.
- If catalog is empty and user wants to sell, use intent "general_qa" and explain they must add products first.
- Match catalog names exactly (case-insensitive). Fuzzy match only for obvious Hindi/English variants (chai=tea).

Classify the intent into one of:
1. "record_sale" -> Selling catalog items (e.g. "2 chai 40 rs", "1 burger becha")
2. "add_to_catalog" -> Adding new items (e.g. "menu mein butter chicken add karo 350 rupaye")
3. "list_catalog" -> Show all menu/catalog items (e.g. "menu dikhao", "catalog batao", "kitne items hain")
4. "search_catalog" -> Find specific item in catalog (e.g. "coffee ka price kya hai", "burger dikhao")
5. "check_payment_status" -> Payment verification (e.g. "payment aaya kya")
6. "query_pending" -> Pending/unpaid balance (e.g. "kitna baaki hai")
7. "query_daily" -> Today's sales summary (e.g. "aaj kitna collection hua")
8. "general_qa" -> Greetings, help, unclear commands

Output strictly valid JSON:
{{
  "intent": "record_sale" | "add_to_catalog" | "list_catalog" | "search_catalog" | "check_payment_status" | "query_pending" | "query_daily" | "general_qa",
  "product_name": "item name if checking status or searching catalog, else null",
  "items": [
    {{
      "product_name": "item name — must match catalog for sales",
      "quantity": int (default 1),
      "unit_price": float or null,
      "category": "optional category",
      "unit": "optional unit e.g. cup, kg, piece"
    }}
  ],
  "payment_status": "pending" | "paid" | "partial",
  "explanation": "Brief polite reply in Hindi/Hinglish — do NOT include made-up financial numbers."
}}
"""


def _match_catalog_name(name: str, catalog_items: List[str]) -> Optional[str]:
    """Find best catalog match for a spoken product name."""
    if not name or not catalog_items:
        return None
    name_lower = name.strip().lower()
    if name_lower in DEVANAGARI_PRODUCT_MAP:
        name_lower = DEVANAGARI_PRODUCT_MAP[name_lower]

    for prod in catalog_items:
        pl = prod.lower()
        if pl == name_lower:
            return pl
    for prod in catalog_items:
        pl = prod.lower()
        if pl in name_lower or name_lower in pl:
            return pl
    for dev_k, eng_v in DEVANAGARI_PRODUCT_MAP.items():
        if dev_k in name or eng_v == name_lower:
            for prod in catalog_items:
                if prod.lower() == eng_v or eng_v in prod.lower():
                    return prod.lower()
    return None


class BaseLLMProvider:
    name = "base"

    def extract_transaction(self, text: str, catalog_items: Optional[List[str]] = None, merchant_profile: Optional[dict] = None) -> VoiceExtractionResult:
        """Extract transactional intent from text with optional catalog and merchant profile context."""
        raise NotImplementedError

    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        raise NotImplementedError

    def summarize_profile(self, profile: Optional[dict]) -> Dict[str, Any]:
        """Return a lightweight summary of the merchant profile suitable for prompt injection.
        Default implementation infers modules from keys and item counts.
        """
        if not profile:
            return {"modules": [], "summary": "Empty profile"}
        modules = []
        if profile.get("products"):
            modules.append("catalog")
        if profile.get("pricing") or profile.get("currency"):
            modules.append("pricing")
        if profile.get("payment_methods"):
            modules.append("payments")
        if profile.get("loyalty"):
            modules.append("loyalty")
        # Heuristic summary
        summary = f"Merchant has {len(profile.get('products', []))} products" if isinstance(profile.get('products'), list) else "Merchant profile available"
        return {"modules": modules, "summary": summary}

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
                    unit=str(raw_item.get("unit", "")).strip() if raw_item.get("unit") else None,
                )
            )
        return items

    def _parse_extraction_response(self, text: str, data: Dict[str, Any]) -> VoiceExtractionResult:
        return VoiceExtractionResult(
            intent=data.get("intent", "general_qa"),
            product_name=data.get("product_name"),
            items=self._parse_items(data),
            payment_status=data.get("payment_status", "pending"),
            raw_text=text,
            explanation=data.get("explanation"),
        )


class GroqLLMProvider(BaseLLMProvider):
    name = "groq"

    def __init__(self):
        self.client = None
        if settings.GROQ_API_KEY:
            try:
                from groq import Groq
                self.client = Groq(api_key=settings.GROQ_API_KEY)
            except Exception as exc:
                logger.warning("Could not initialize Groq client: %s", exc)

    def extract_transaction(
        self,
        text: str,
        catalog_items: Optional[List[str]] = None,
        merchant_profile: Optional[dict] = None,
        business_type: Optional[str] = None,
        context: str = "terminal",
    ) -> VoiceExtractionResult:
        if not self.client:
            raise RuntimeError("Groq client not configured")

        prompt = _build_extraction_prompt(text, catalog_items, merchant_profile, business_type, context)
        model = settings.GROQ_MODEL or settings.LLM_MODEL
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
            response_text = self._strip_markdown_json(response.choices[0].message.content or "")
            data = json.loads(response_text)
            return self._parse_extraction_response(text, data)
        except Exception as exc:
            logger.warning("Groq extraction failed: %s", exc)
            raise

    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        if not self.client:
            raise RuntimeError("Groq client not configured")

        prompt = f"""
You are VoiceLedger AI. Answer ONLY using the exact numbers in Live Store Financial Facts below.
Do NOT invent or estimate any amounts. If data is missing, say you don't have that information.
Reply in 1-2 sentences of natural Hindi/Hinglish.

Live Store Financial Facts:
{json.dumps(context_data, indent=2, default=str)}

Merchant Query: "{query}"
"""
        model = settings.GROQ_MODEL or settings.LLM_MODEL
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("Groq answer generation failed: %s", exc)
            raise

    def refine_for_speech(self, text: str, lang: str = "hi") -> str:
        if not self.client or not settings.TTS_USE_LLM_REFINEMENT:
            return text
        prompt = f"""
Convert this shopkeeper assistant message into natural spoken {'Hindi' if lang.startswith('hi') else 'English'}.
Rules: keep it under 2 sentences, remove URLs/emojis/markdown, convert Rs/₹ to "rupaye", no bullet points.
Return ONLY the spoken text, nothing else.

Message: {text}
"""
        model = settings.GROQ_MODEL or settings.LLM_MODEL
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                timeout=10,
            )
            refined = (response.choices[0].message.content or "").strip()
            return refined if refined else text
        except Exception:
            return text

    def summarize_profile(self, profile: Optional[dict]) -> Dict[str, Any]:
        if not self.client or not profile:
            return super().summarize_profile(profile)
        prompt = f"Summarize this merchant profile in JSON with modules and a short summary: {json.dumps(profile, default=str)}"
        model = settings.GROQ_MODEL or settings.LLM_MODEL
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
            txt = self._strip_markdown_json(response.choices[0].message.content or "")
            try:
                return json.loads(txt)
            except Exception:
                return {"modules": [], "summary": txt}
        except Exception as exc:
            logger.warning("Groq summarize_profile failed: %s", exc)
            return super().summarize_profile(profile)


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

    def extract_transaction(
        self,
        text: str,
        catalog_items: Optional[List[str]] = None,
        merchant_profile: Optional[dict] = None,
        business_type: Optional[str] = None,
        context: str = "terminal",
    ) -> VoiceExtractionResult:
        if not self.client:
            raise RuntimeError("Gemini client not configured")

        prompt = _build_extraction_prompt(text, catalog_items, merchant_profile, business_type, context)
        model = settings.GEMINI_MODEL or settings.LLM_MODEL
        try:
            response = self.client.models.generate_content(model=model, contents=prompt)
            response_text = self._strip_markdown_json(response.text)
            data = json.loads(response_text)
            return self._parse_extraction_response(text, data)
        except Exception as exc:
            logger.warning("Gemini extraction failed: %s", exc)
            raise

    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        if not self.client:
            raise RuntimeError("Gemini client not configured")

        prompt = f"""
You are VoiceLedger AI. Answer ONLY using the exact numbers in Live Store Financial Facts below.
Do NOT invent or estimate any amounts. Reply in 1-2 sentences of natural Hindi/Hinglish.

Live Store Financial Facts:
{json.dumps(context_data, indent=2, default=str)}

Merchant Query: "{query}"
"""
        model = settings.GEMINI_MODEL or settings.LLM_MODEL
        try:
            response = self.client.models.generate_content(model=model, contents=prompt)
            return response.text.strip()
        except Exception as exc:
            logger.warning("Gemini answer generation failed: %s", exc)
            raise

    def refine_for_speech(self, text: str, lang: str = "hi") -> str:
        if not self.client or not settings.TTS_USE_LLM_REFINEMENT:
            return text
        prompt = f"""
Convert this message into natural spoken {'Hindi' if lang.startswith('hi') else 'English'} for TTS.
Keep under 2 sentences, no URLs/emojis. Return ONLY spoken text.

Message: {text}
"""
        model = settings.GEMINI_MODEL or settings.LLM_MODEL
        try:
            response = self.client.models.generate_content(model=model, contents=prompt)
            refined = (response.text or "").strip()
            return refined if refined else text
        except Exception:
            return text

    def summarize_profile(self, profile: Optional[dict]) -> Dict[str, Any]:
        # Use a short prompt to summarize the merchant profile if client present
        if not self.client or not profile:
            return super().summarize_profile(profile)
        prompt = f"Summarize this merchant profile in JSON with modules and a short summary: {json.dumps(profile, default=str)}"
        try:
            resp = self.client.models.generate_content(model=settings.LLM_MODEL, contents=prompt)
            txt = self._strip_markdown_json(resp.text or "")
            try:
                parsed = json.loads(txt)
                return parsed
            except Exception:
                return {"modules": [], "summary": txt}
        except Exception as exc:
            logger.warning("Gemini summarize_profile failed: %s", exc)
            return super().summarize_profile(profile)


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

    def extract_transaction(self, text: str, catalog_items: Optional[List[str]] = None, merchant_profile: Optional[dict] = None) -> VoiceExtractionResult:
        if not self.client:
            raise RuntimeError("OpenAI client not configured")

        catalog_prompt = f"Merchant product catalog: {', '.join(catalog_items)}" if catalog_items else ""
        profile_prompt = f"Merchant Profile: {json.dumps(merchant_profile, default=str)}" if merchant_profile else ""
        prompt = f"""
You are VoiceLedger AI. Extract merchant intent from: "{text}".
{catalog_prompt}
{profile_prompt}
Output JSON with: intent, product_name, items, payment_status, explanation.
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

        prompt = f"Answer merchant query in Hindi/Hinglish. Data: {json.dumps(context_data, default=str)} Query: {query}"
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

    def summarize_profile(self, profile: Optional[dict]) -> Dict[str, Any]:
        if not self.client or not profile:
            return super().summarize_profile(profile)
        prompt = f"Summarize this merchant profile in JSON with modules and a short summary: {json.dumps(profile, default=str)}"
        try:
            response = self.client.responses.create(
                model=settings.LLM_MODEL,
                input=prompt,
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
            txt = self._strip_markdown_json(response.output_text or "")
            try:
                return json.loads(txt)
            except Exception:
                return {"modules": [], "summary": txt}
        except Exception as exc:
            logger.warning("OpenAI summarize_profile failed: %s", exc)
            return super().summarize_profile(profile)


class MockLLMProvider(BaseLLMProvider):
    name = "mock"

    def __init__(self):
        self.client = None

    def extract_transaction(self, text: str, catalog_items: Optional[List[str]] = None, merchant_profile: Optional[dict] = None) -> VoiceExtractionResult:
        return VoiceExtractionResult(
            intent="general_qa",
            raw_text=text,
            items=[],
            payment_status="pending",
            explanation="VoiceLedger Assistant active.",
        )

    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        return "VoiceLedger AI active."

    def summarize_profile(self, profile: Optional[dict]) -> Dict[str, Any]:
        return super().summarize_profile(profile)


class LLMService:
    """
    Intelligent Conversational Agent & Intent Extraction Service.
    Cascade: Groq (primary) → Gemini (fallback) → Rule-based engine.
    """

    def __init__(self):
        self.groq = GroqLLMProvider()
        self.gemini = GeminiLLMProvider()
        self.openai = OpenAIProvider()
        self.mock = MockLLMProvider()

        provider_name = (settings.LLM_PROVIDER or "groq").lower()
        if provider_name == "groq":
            self.provider = self.groq
        elif provider_name == "gemini":
            self.provider = self.gemini
        elif provider_name == "openai":
            self.provider = self.openai
        else:
            self.provider = self.mock

        self.client = getattr(self.provider, "client", None) or getattr(self.gemini, "client", None)

    def _extract_with_fallback(
        self,
        text: str,
        catalog_items: Optional[List[str]],
        merchant_profile: Optional[dict],
        business_type: Optional[str],
        context: str,
    ) -> VoiceExtractionResult:
        """Try Groq first, then Gemini, then rule-based parser."""
        errors = []
        for provider in (self.groq, self.gemini):
            if not getattr(provider, "client", None):
                continue
            try:
                result = provider.extract_transaction(
                    text, catalog_items, merchant_profile, business_type, context
                )
                logger.info("LLM extraction via %s succeeded", provider.name)
                return result
            except Exception as exc:
                errors.append(f"{provider.name}: {exc}")
                logger.warning("LLM provider %s failed: %s", provider.name, exc)

        if settings.LLM_PROVIDER == "openai" and self.openai.client:
            try:
                return self.openai.extract_transaction(text, catalog_items, merchant_profile)
            except Exception as exc:
                errors.append(f"openai: {exc}")

        logger.warning("All LLM providers failed (%s), using rule-based parser", "; ".join(errors))
        return self._dynamic_parse(text, catalog_items or [], merchant_profile, context)

    def extract_transaction(
        self,
        text: str,
        catalog_items: Optional[List[str]] = None,
        merchant_profile: Optional[dict] = None,
        business_type: Optional[str] = None,
        context: str = "terminal",
    ) -> VoiceExtractionResult:
        text_clean = text.strip()
        if not text_clean:
            return VoiceExtractionResult(
                intent="unknown",
                raw_text=text,
                explanation="Koi aawaz ya text nahi mila. Kripya dobara bolein.",
            )

        result = self._extract_with_fallback(
            text_clean, catalog_items, merchant_profile, business_type, context
        )
        return self.validate_extraction(result, catalog_items or [])

    def validate_extraction(
        self, extraction: VoiceExtractionResult, catalog_items: List[str]
    ) -> VoiceExtractionResult:
        """Ground extraction against catalog to reduce hallucinated sales."""
        if extraction.intent != "record_sale" or not extraction.items:
            return extraction

        if not catalog_items:
            return VoiceExtractionResult(
                intent="general_qa",
                raw_text=extraction.raw_text,
                items=[],
                explanation=(
                    "Aapke catalog me abhi koi product nahi hai. "
                    "Pehle Menu & Items tab me product add karein, ya bolein: 'Menu mein chai add karo 20 rupaye'."
                ),
            )

        validated: List[VoiceItemExtracted] = []
        unknown: List[str] = []

        for item in extraction.items:
            matched = _match_catalog_name(item.product_name, catalog_items)
            if matched:
                validated.append(
                    VoiceItemExtracted(
                        product_name=matched,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        category=item.category,
                        unit=item.unit,
                    )
                )
            elif item.unit_price is not None and item.unit_price > 0:
                validated.append(item)
            else:
                unknown.append(item.product_name)

        if unknown and not validated:
            names = ", ".join(unknown)
            return VoiceExtractionResult(
                intent="general_qa",
                raw_text=extraction.raw_text,
                items=[],
                explanation=(
                    f"'{names}' aapke catalog me nahi mila. "
                    f"Pehle item add karein ya catalog me maujood naam bolein: {', '.join(catalog_items[:8])}."
                ),
            )

        if unknown:
            names = ", ".join(unknown)
            extraction.explanation = (
                f"Kuch items catalog me nahi mile ({names}) — unhe skip kiya. "
                + (extraction.explanation or "")
            )

        extraction.items = validated
        return extraction

    def answer_query(self, query: str, context_data: Dict[str, Any], use_llm: bool = False) -> str:
        """Deterministic answers by default; LLM only when explicitly requested."""
        if not use_llm:
            return self._answer_from_context(query, context_data)

        for provider in (self.groq, self.gemini):
            if not getattr(provider, "client", None):
                continue
            try:
                return provider.answer_query(query, context_data)
            except Exception:
                continue
        return self._answer_from_context(query, context_data)

    def refine_for_speech(self, text: str, lang: str = "hi") -> str:
        for provider in (self.groq, self.gemini):
            if hasattr(provider, "refine_for_speech") and getattr(provider, "client", None):
                try:
                    return provider.refine_for_speech(text, lang)
                except Exception:
                    continue
        return text

    def summarize_profile(self, profile: Optional[dict]) -> Dict[str, Any]:
        for provider in (self.groq, self.gemini, self.openai):
            if getattr(provider, "client", None):
                try:
                    return provider.summarize_profile(profile)
                except Exception:
                    continue
        return self.mock.summarize_profile(profile)

    def _dynamic_parse(
        self,
        text: str,
        catalog_items: List[str],
        merchant_profile: Optional[dict] = None,
        context: str = "terminal",
    ) -> VoiceExtractionResult:
        """
        High-Accuracy Rule-Based & Semantic NLP Engine for Hindi / Hinglish.
        Accurately separates Status Queries, Add-to-Catalog, Pending Balances, Greetings, and Sales.
        """
        lower_text = text.lower().strip()

        # ── 1. GREETINGS & HELP ──────────────────────────────────────────
        greetings = ["namaste", "hello", "hi", "kaise ho", "kya kar sakte ho", "help", "options", "madad", "नमस्ते", "हेल्प"]
        if any(lower_text.startswith(g) or lower_text == g for g in greetings) and len(lower_text.split()) <= 4:
            return VoiceExtractionResult(
                intent="general_qa",
                raw_text=text,
                explanation="Namaste! Main aapka VoiceLedger AI assistant hoon. Aap mujhse sale record karwa sakte hain, payment status verify kar sakte hain, ya menu me naya item add kar sakte hain.",
            )

        # ── 2. PAYMENT ARRIVAL & STATUS VERIFICATION ──────────────────────
        payment_check_keywords = [
            "payment aaya", "paisa aaya", "pay hua", "check payment", "payment status",
            "status kya hai", "aaya ya nahi", "did payment arrive", "received or not",
            "verify payment", "payment mila", "paisa mila", "payment check", "check karo",
            "kya status hai", "order status", "status check", "payment hua", "payment ka kya",
            "पेमेंट आया", "पैसा आया", "पेमेंट मिला", "पैसा मिला", "स्टेटस क्या है", "पेमेंट चेक", "स्टेटस",
        ]
        is_payment_check = any(k in lower_text for k in payment_check_keywords)
        if is_payment_check:
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
                explanation=f"{matched_prod or 'Recent order'} ka payment status live check kiya ja raha hai...",
            )

        # ── 3. PENDING BALANCES & RECEIVABLES ─────────────────────────────
        pending_keywords = [
            "pending", "baaki", "baki", "lena hai", "outstanding", "udhaar", "balance",
            "kitna baaki", "kitna pending", "bakaya", "बाकी", "पेंडिंग", "उधार",
        ]
        if any(k in lower_text for k in pending_keywords):
            return VoiceExtractionResult(
                intent="query_pending",
                raw_text=text,
                explanation="Aapke total pending payments check kiye ja rahe hain.",
            )

        # ── 4. DAILY SALES & COLLECTION SUMMARY ───────────────────────────
        summary_keywords = [
            "aaj ka sale", "today sales", "kitna collect", "daily summary", "aaj kitna hua",
            "total sale", "total collection", "aaj ki bikri", "hisab", "khata", "report",
            "summary batao", "collection kitna", "आज का सेल", "हिसाब", "खाता",
        ]
        if any(k in lower_text for k in summary_keywords):
            return VoiceExtractionResult(
                intent="query_daily",
                raw_text=text,
                explanation="Aaj ki total sales aur collection summary check ki ja rahi hai.",
            )

        # ── 4b. LIST / SEARCH CATALOG ─────────────────────────────────────
        list_keywords = [
            "menu dikhao", "catalog dikhao", "catalog batao", "menu batao", "kitne items",
            "sab items", "poora menu", "list catalog", "show menu", "show catalog",
            "मेन्यू दिखाओ", "कैटलॉग दिखाओ",
        ]
        if any(k in lower_text for k in list_keywords):
            return VoiceExtractionResult(
                intent="list_catalog",
                raw_text=text,
                explanation="Aapke catalog ke saare items dikhaye ja rahe hain.",
            )

        search_keywords = ["ka price", "ki keemat", "kitne ka", "dikhao", "search", "find", "kahan hai"]
        if any(k in lower_text for k in search_keywords) and catalog_items:
            matched = None
            for prod in sorted(catalog_items, key=len, reverse=True):
                if prod.lower() in lower_text:
                    matched = prod.lower()
                    break
            if matched:
                return VoiceExtractionResult(
                    intent="search_catalog",
                    product_name=matched,
                    raw_text=text,
                    explanation=f"'{matched}' catalog me dhoondha ja raha hai.",
                )

        # ── 5. ADD ITEM TO CATALOG / MENU ────────────────────────────────
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
            price_found = 0.0
            price_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:each|per|rupaye|rs|rupya|inr|/-|रुपये|रुपया|रु)", lower_text)
            if price_match:
                price_found = float(price_match.group(1))
            else:
                num_match = re.search(r"\b(\d+)\b", lower_text)
                if num_match:
                    price_found = float(num_match.group(1))

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

        # ── 6. RECORD PRODUCT SALE ─────────────────────────────────────────
        if not catalog_items:
            sale_verbs = ["becha", "sold", "diye", "diya", "pack karo", "order", "bill", "sell", "बिका", "बेचा", "दिया"]
            if any(v in lower_text for v in sale_verbs) or re.search(r"\b\d+\b", lower_text):
                return VoiceExtractionResult(
                    intent="general_qa",
                    raw_text=text,
                    items=[],
                    explanation=(
                        "Aapke catalog me abhi koi product nahi hai. "
                        "Pehle Menu & Items tab me product add karein."
                    ),
                )

        items: List[VoiceItemExtracted] = []
        price_found = None
        price_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:each|per|rupaye|rs|rupya|inr|/-|रुपये|रुपया|रु)", lower_text)
        if price_match:
            price_found = float(price_match.group(1))

        # Check Devanagari product names
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

        # Check Catalog product names in database
        if not found_devanagari:
            for prod in sorted(catalog_items, key=len, reverse=True):
                if prod.lower() in lower_text:
                    qty = 1
                    qty_pattern = rf"(\S+)\s+{re.escape(prod.lower())}"
                    qm = re.search(qty_pattern, lower_text)
                    if qm:
                        qty = HINDI_NUMBERS.get(qm.group(1).lower(), 1)
                    items.append(VoiceItemExtracted(product_name=prod.lower(), quantity=qty, unit_price=price_found))

        # Check explicit sale verbs if not already matched
        sale_verbs = ["becha", "sold", "diye", "diya", "pack karo", "order", "bill", "sell", "बिका", "बेचा", "दिया"]
        has_sale_verb = any(v in lower_text for v in sale_verbs)

        if not items and has_sale_verb:
            qty = 1
            qty_match = re.search(r"\b(\d+|ek|do|teen|char|chaar|paanch|one|two|three|four|five|एक|दो|तीन|चार|पांच)\b", lower_text)
            if qty_match:
                qty_word = qty_match.group(1).lower()
                qty = HINDI_NUMBERS.get(qty_word, int(qty_word) if qty_word.isdigit() else 1)

            # Only accept sale if a catalog item is mentioned
            for prod in sorted(catalog_items, key=len, reverse=True):
                if prod.lower() in lower_text:
                    items.append(VoiceItemExtracted(product_name=prod.lower(), quantity=qty, unit_price=price_found))
                    break

        if items:
            items_str = ", ".join([f"{it.quantity}x {it.product_name}" for it in items])
            explanation = f"{items_str} ka sale record kiya gaya."
            return VoiceExtractionResult(
                intent="record_sale",
                items=items,
                payment_status="pending",
                raw_text=text,
                explanation=explanation,
            )

        # ── 7. FALLBACK / GENERAL QUERY ──────────────────────────────────
        return VoiceExtractionResult(
            intent="general_qa",
            raw_text=text,
            explanation=f"Aapne poocha: '{text}'. Main aapke live store ledger aur payment status ki jankari de sakta hoon.",
        )

    def _answer_from_context(self, query: str, context_data: Dict[str, Any]) -> str:
        q_lower = query.lower()

        # 1. Pending query
        if any(w in q_lower for w in ["pending", "baaki", "baki", "lena hai", "outstanding", "udhaar", "बाकी"]):
            pending_amt = context_data.get("total_outstanding", 0.0)
            pending_count = context_data.get("pending_count", 0) + context_data.get("partial_count", 0)
            if pending_amt <= 0:
                return "Badhiya! Aapka koi bhi payment pending nahi hai. Saare bills clear hain."
            return f"Aapka kul Rs. {pending_amt:,.2f} pending hai {pending_count} sales ke liye. Aap recovery queue se reminder bhej sakte hain."

        # 2. Daily sales & collection summary
        if any(w in q_lower for w in ["sale", "today", "aaj", "collect", "summary", "bikri", "aaj ka", "आज"]):
            today_sales = context_data.get("today_sales", 0.0)
            collected = context_data.get("total_collected", 0.0)
            total_tx = context_data.get("total_transactions", 0)
            return f"Aaj ka total sale Rs. {today_sales:,.2f} hai ({total_tx} transactions). Kul Rs. {collected:,.2f} collect ho chuka hai."

        # 3. Payment Status Check
        if any(w in q_lower for w in ["status", "payment", "paisa", "check", "pay"]):
            paid_count = context_data.get("paid_count", 0)
            pending_count = context_data.get("pending_count", 0)
            total_collected = context_data.get("total_collected", 0.0)
            return f"Aapke {paid_count} payments receive ho chuke hain (Rs. {total_collected:,.2f} collected), aur {pending_count} payments abhi pending hain."

        # 4. Greetings
        if any(w in q_lower for w in ["namaste", "hello", "hi", "help", "kya kar"]):
            return "Namaste! Main aapka VoiceLedger AI assistant hoon. Aap mujhse sale record karwa sakte hain, payment status check kar sakte hain, ya catalog manage kar sakte hain."

        # Default accurate financial context response
        total_coll = context_data.get("total_collected", 0.0)
        total_out = context_data.get("total_outstanding", 0.0)
        return f"Aapke store me kul Rs. {total_coll:,.2f} collect hua hai aur Rs. {total_out:,.2f} outstanding balance hai."


llm_service = LLMService()
