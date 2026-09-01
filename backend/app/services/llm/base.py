import json
from typing import Any, Dict, List, Optional
from backend.app.schemas.voice import VoiceExtractionResult, VoiceItemExtracted


class BaseLLMProvider:
    name = "base"

    def extract_transaction(
        self,
        text: str,
        catalog_items: Optional[List[str]] = None,
        merchant_profile: Optional[dict] = None,
        business_type: Optional[str] = None,
        context: str = "terminal",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> VoiceExtractionResult:
        raise NotImplementedError

    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        raise NotImplementedError

    def refine_for_speech(self, text: str, lang: str = "hi") -> str:
        return text

    def summarize_profile(self, profile: Optional[dict]) -> Dict[str, Any]:
        if not profile:
            return {"modules": [], "summary": "Empty profile"}
        return {"modules": ["catalog", "pricing", "payments"], "summary": "Store profile active"}

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
            customer_name=data.get("customer_name"),
            items=self._parse_items(data),
            payment_status=data.get("payment_status", "pending"),
            raw_text=text,
            explanation=data.get("explanation"),
        )
