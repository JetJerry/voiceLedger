from sqlalchemy.orm import Session
from backend.app.schemas.voice import VoiceProcessRequest, VoiceProcessResponse
from backend.app.agentic.graph import run_voiceledger_agent_workflow


class MerchantAgent:
    """
    Agentic LangGraph Orchestrator with LangSmith Tracing:
    - Coordinates stateful multi-node LangGraph execution.
    - Applies guardrails, entity extraction, deterministic database mutations, and Neural TTS.
    """
    def process_merchant_command(self, db: Session, request: VoiceProcessRequest) -> VoiceProcessResponse:
        return run_voiceledger_agent_workflow(db, request)


merchant_agent = MerchantAgent()
