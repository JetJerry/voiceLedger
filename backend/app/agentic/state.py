from typing import TypedDict, List, Dict, Any, Optional
from backend.app.schemas.voice import VoiceItemExtracted, VoiceExtractionResult


class VoiceLedgerState(TypedDict):
    """
    State for VoiceLedger's LangGraph Agent Workflow.
    Preserves input parameters, enriched context, extraction results,
    guardrail validations, tool execution results, and speech audio.
    """
    # ── 1. Input Command & Metadata ──
    raw_text: str
    merchant_id: Optional[int]
    context: str                  # "terminal" | "catalog" | "sales" | "admin"
    voice_lang: str               # "hi" | "en"
    speak_response: bool
    history: List[Dict[str, str]]
    
    # ── 2. Enriched Context ──
    catalog_items: List[str]
    product_map: Dict[str, Any]
    business_type: str
    merchant_profile: Optional[Dict[str, Any]]
    
    # ── 3. Extraction & Classification ──
    intent: str
    product_name: Optional[str]
    items: List[Dict[str, Any]]
    total_amount: Optional[float]
    customer_name: Optional[str]
    is_credit: bool
    explanation: Optional[str]
    attributes: Dict[str, Any]
    extraction_result: Optional[Dict[str, Any]]
    
    # ── 4. Guardrails & Validation ──
    is_valid: bool
    validation_error: Optional[str]
    action_taken: str
    
    # ── 5. Tool Execution Results ──
    tool_result: Dict[str, Any]
    
    # ── 6. Final Outputs ──
    agent_reply: str
    audio_base64: Optional[str]
