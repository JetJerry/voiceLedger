"""
VoiceLedger Canonical Voice Talkback API (v1).

Merchant conversational interface for natural language sales recording,
catalog exploration, and financial queries via AI agents and Neural TTS.
Strictly isolated to authenticated merchant context.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.api.deps import get_current_merchant
from backend.app.models.merchant import Merchant
from backend.app.schemas.voice import VoiceProcessRequest, VoiceProcessResponse
from backend.app.agentic.graph import run_voiceledger_agent_workflow
from backend.app.services.voice_service import voice_service
from backend.app.services.tts_service import tts_service

router = APIRouter(prefix="/voice", tags=["Voice Talkback v1"])


@router.post("/process-text", response_model=VoiceProcessResponse)
def process_voice_text(
    request: VoiceProcessRequest,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """
    Process typed or spoken merchant command through LangGraph AI agent.
    Guaranteed tenant-isolated to current_merchant.id.
    """
    # Force merchant context from authenticated token
    request.merchant_id = str(current_merchant.id)
    return run_voiceledger_agent_workflow(db, request)


@router.post("/process-audio", response_model=VoiceProcessResponse)
async def process_voice_audio(
    file: UploadFile = File(...),
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """
    Upload microphone audio recording, transcribe via STT, and execute merchant command.
    """
    try:
        audio_bytes = await file.read()
        mime_type = file.content_type or "audio/webm"

        # Transcribe audio
        extraction = voice_service.process_audio_bytes(audio_bytes, mime_type=mime_type)
        transcript = extraction.raw_text or "Voice command"

        req = VoiceProcessRequest(
            text=transcript,
            merchant_id=str(current_merchant.id),
        )
        return run_voiceledger_agent_workflow(db, req)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio processing error: {str(exc)}",
        ) from exc


@router.get("/speak")
async def speak_text(
    text: str = Query(..., description="Text to synthesize to speech"),
    lang: str = Query("hi", description="Language: 'hi' (Hindi) or 'en' (English)"),
    voice: Optional[str] = Query(None, description="Optional neural voice identifier"),
):
    """
    Direct Neural TTS endpoint: Streams MP3 audio of Hindi or English text.
    """
    try:
        audio_bytes = await tts_service.generate_speech_async(text=text, lang=lang, voice=voice)
        return Response(content=audio_bytes, media_type="audio/mp3")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS synthesis error: {str(exc)}",
        ) from exc
