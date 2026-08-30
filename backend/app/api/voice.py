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
