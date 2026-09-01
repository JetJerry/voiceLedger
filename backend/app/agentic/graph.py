import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, START, END
from langsmith import traceable

from backend.app.agentic.state import VoiceLedgerState
from backend.app.agentic.nodes import (
    enrich_context_node,
    extract_intent_node,
    guardrails_validator_node,
    execute_tool_node,
    generate_response_node,
    synthesize_tts_node,
)
from backend.app.agentic.llm_factory import setup_langsmith_tracing
from backend.app.schemas.voice import VoiceProcessRequest, VoiceProcessResponse, VoiceExtractionResult, VoiceItemExtracted

logger = logging.getLogger("voiceledger.langgraph.graph")

# Ensure LangSmith tracing is active
setup_langsmith_tracing()


def _route_after_guardrails(state: VoiceLedgerState) -> str:
    """
    Conditional routing:
    If validation fails (e.g. catalog empty), skip tool execution and generate explanation directly.
    """
    if not state.get("is_valid", True):
        return "generate_response"
    return "execute_tool"


def build_voiceledger_graph(db: Session):
    """
    Constructs the stateful LangGraph workflow for VoiceLedger.
    """
    graph = StateGraph(VoiceLedgerState)

    # Add Nodes
    graph.add_node("enrich_context", lambda state: enrich_context_node(state, db))
    graph.add_node("extract_intent", extract_intent_node)
    graph.add_node("guardrails_validator", guardrails_validator_node)
    graph.add_node("execute_tool", lambda state: execute_tool_node(state, db))
    graph.add_node("generate_response", generate_response_node)
    graph.add_node("synthesize_tts", synthesize_tts_node)

    # Define Edges & Flow
    graph.add_edge(START, "enrich_context")
    graph.add_edge("enrich_context", "extract_intent")
    graph.add_edge("extract_intent", "guardrails_validator")

    # Conditional branching from guardrails
    graph.add_conditional_edges(
        "guardrails_validator",
        _route_after_guardrails,
        {
            "execute_tool": "execute_tool",
            "generate_response": "generate_response",
        }
    )

    graph.add_edge("execute_tool", "generate_response")
    graph.add_edge("generate_response", "synthesize_tts")
    graph.add_edge("synthesize_tts", END)

    return graph.compile()


@traceable(name="voiceledger_agent_workflow", run_type="chain")
def run_voiceledger_agent_workflow(
    db: Session,
    request: VoiceProcessRequest,
    merchant_id: Optional[int] = None
) -> VoiceProcessResponse:
    """
    Executes the compiled LangGraph workflow with deep LangSmith observability.
    Returns standard VoiceProcessResponse for complete API backward compatibility.
    """
    compiled_app = build_voiceledger_graph(db)

    # Initial State
    initial_state: VoiceLedgerState = {
        "raw_text": request.text,
        "merchant_id": merchant_id,
        "context": request.context or "terminal",
        "voice_lang": request.voice_lang or "hi",
        "speak_response": request.speak_response if request.speak_response is not None else True,
        "history": request.history or [],
        
        "catalog_items": [],
        "product_map": {},
        "business_type": "General Retail",
        "merchant_profile": None,
        
        "intent": "general_qa",
        "product_name": None,
        "items": [],
        "total_amount": None,
        "customer_name": None,
        "is_credit": False,
        "explanation": None,
        "attributes": {},
        "extraction_result": None,
        
        "is_valid": True,
        "validation_error": None,
        "action_taken": "PENDING",
        
        "tool_result": {},
        "agent_reply": "",
        "audio_base64": None,
    }

    # Invoke Graph
    final_state: VoiceLedgerState = compiled_app.invoke(initial_state)

    # Map to VoiceExtractionResult
    items_extracted = [
        VoiceItemExtracted(
            product_name=it.get("product_name", "item"),
            quantity=it.get("quantity", 1),
            unit_price=it.get("unit_price"),
            category=it.get("category"),
            unit=it.get("unit"),
        )
        for it in final_state.get("items", [])
    ]

    extraction = VoiceExtractionResult(
        intent=final_state.get("intent", "general_qa"),
        items=items_extracted,
        customer_name=final_state.get("customer_name"),
        payment_status="pending" if not final_state.get("is_credit") else "credit",
        raw_text=request.text,
        explanation=final_state.get("explanation"),
    )

    return VoiceProcessResponse(
        extraction=extraction,
        agent_reply=final_state.get("agent_reply", ""),
        audio_base64=final_state.get("audio_base64"),
        sale=final_state.get("tool_result", {}).get("sale"),
        action_taken=final_state.get("action_taken", "COMPLETED"),
    )
