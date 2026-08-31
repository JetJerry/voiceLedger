from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.voice import VoiceProcessRequest, VoiceProcessResponse
from backend.app.services.voice_service import voice_service
from backend.app.services.tts_service import tts_service
from backend.app.agents.merchant_agent import merchant_agent

router = APIRouter(prefix="/voice", tags=["Voice & Natural Language"])


@router.post("/process-text", response_model=VoiceProcessResponse)
def process_voice_text(request: VoiceProcessRequest, db: Session = Depends(get_db)):
    """
    Process merchant spoken or typed text through AI understanding, guarded agent tools, and neural TTS synthesis.
    """
    return merchant_agent.process_merchant_command(db, request)


@router.post("/process-audio", response_model=VoiceProcessResponse)
async def process_voice_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload and process an audio recording from the merchant's microphone.
    """
    try:
        audio_bytes = await file.read()
        mime_type = file.content_type or "audio/webm"
        
        # Extract via VoiceService
        extraction = voice_service.process_audio_bytes(audio_bytes, mime_type=mime_type)
        
        # Forward extracted text to MerchantAgent
        req = VoiceProcessRequest(text=extraction.raw_text or "Audio command")
        return merchant_agent.process_merchant_command(db, req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio processing error: {str(e)}")


@router.get("/speak")
async def speak_text(
    text: str = Query(..., description="Text to speak"),
    lang: str = Query("hi", description="Language code: hi (Hindi) or en (English)"),
    voice: str = Query(None, description="Optional neural voice identifier")
):
    """
    Direct Neural TTS endpoint: Streams MP3 audio of Hindi or English text.
    """
    try:
        audio_bytes = await tts_service.generate_speech_async(text=text, lang=lang, voice=voice)
        return Response(content=audio_bytes, media_type="audio/mp3")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS synthesis error: {str(e)}")


# ── Live Voice Soundbox Payment Announcements ────────────────────────

@router.get("/payment-announcements")
def get_payment_announcements(
    merchant_id: Optional[int] = Query(None, description="Filter by merchant ID (defaults to active store)"),
    db: Session = Depends(get_db),
):
    """
    Returns unacknowledged payment arrival events for the store.
    Used by the frontend speaker to announce customer payments in real-time (Soundbox mode).
    """
    from backend.app.services.payment_announcement_service import payment_announcement_service
    from backend.app.services.sales_service import sales_service

    if merchant_id is None:
        active_m = sales_service.get_or_create_merchant(db)
        merchant_id = active_m.id if active_m else 1

    return payment_announcement_service.get_unannounced_for_merchant(merchant_id=merchant_id)


@router.post("/payment-announcements/{announcement_id}/ack")
def acknowledge_payment_announcement(announcement_id: str):
    """
    Marks a payment arrival announcement as acknowledged after speaker playback.
    """
    from backend.app.services.payment_announcement_service import payment_announcement_service
    success = payment_announcement_service.acknowledge_announcement(announcement_id)
    return {"acknowledged": success, "id": announcement_id}
