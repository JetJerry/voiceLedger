import io
import re
import asyncio
import base64
import logging
from typing import Optional
import edge_tts
from gtts import gTTS

from backend.app.config import settings

logger = logging.getLogger("voiceledger.tts")

# High-Speed Neural Voices
VOICE_HINDI_MALE = "hi-IN-MadhurNeural"
VOICE_HINDI_FEMALE = "hi-IN-SwaraNeural"
VOICE_ENGLISH_INDIAN = "en-IN-PrabhatNeural"
VOICE_ENGLISH_FEMALE = "en-IN-NeerjaNeural"


def clean_text_for_speech(text: str) -> str:
    """
    Clean text for natural, fluent verbal speech:
    - Strips URLs (so long web links aren't read out letter by letter)
    - Strips emojis and icons
    - Converts currency abbreviations (Rs. 100 / ₹100 -> 100 rupaye)
    - Cleans markdown markers
    """
    if not text:
        return ""
    
    cleaned = re.sub(r'https?://\S+', '', text)
    cleaned = re.sub(r'Razorpay Payment Link ready:?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(?:Rs\.?|₹|INR)\s*(\d+(?:\.\d+)?)', r'\1 rupaye', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'[\U00010000-\U0010ffff]', '', cleaned)
    cleaned = re.sub(r'[\u2600-\u27bf]', '', cleaned)
    cleaned = re.sub(r'[✅⏳⚠️❌🎙️⚡💰🛍️🔍☕📚➕📞]', '', cleaned)
    cleaned = re.sub(r'[*_#`~]', '', cleaned)
    cleaned = re.sub(r'\([A-Z\s]+\)', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


class HFTTSEngine:
    """Lazy-loaded HuggingFace MMS-TTS model (facebook/mms-tts-hin etc.)."""

    def __init__(self):
        self._pipeline = None
        self._model_id = settings.HF_TTS_MODEL

    def _ensure_loaded(self):
        if self._pipeline is not None:
            return
        try:
            import torch
            from transformers import pipeline

            device = 0 if torch.cuda.is_available() else -1
            self._pipeline = pipeline(
                "text-to-speech",
                model=self._model_id,
                device=device,
            )
            logger.info("HF TTS model loaded: %s", self._model_id)
        except Exception as exc:
            logger.warning("Could not load HF TTS model %s: %s", self._model_id, exc)
            raise

    def synthesize(self, text: str) -> bytes:
        self._ensure_loaded()
        import soundfile as sf
        import numpy as np

        output = self._pipeline(text)
        audio = output.get("audio")
        sampling_rate = output.get("sampling_rate", 16000)

        if audio is None:
            return b""

        if hasattr(audio, "numpy"):
            audio = audio.numpy()
        audio_arr = np.asarray(audio, dtype=np.float32)

        buf = io.BytesIO()
        sf.write(buf, audio_arr, sampling_rate, format="WAV")
        buf.seek(0)
        return buf.read()


class TTSService:
    """
    High-Performance Text-to-Speech Service.
    Cascade: Edge-TTS Neural → HuggingFace MMS-TTS → gTTS.
    Optional LLM refinement polishes agent text before synthesis.
    """

    def __init__(self):
        self._hf_engine: Optional[HFTTSEngine] = None

    def _get_hf_engine(self) -> HFTTSEngine:
        if self._hf_engine is None:
            self._hf_engine = HFTTSEngine()
        return self._hf_engine

    async def _edge_tts(self, spoken_text: str, lang: str, voice: Optional[str]) -> bytes:
        selected_voice = voice
        if not selected_voice:
            selected_voice = VOICE_HINDI_MALE if lang.startswith("hi") else VOICE_ENGLISH_INDIAN

        communicate = edge_tts.Communicate(spoken_text, selected_voice, rate="+5%")
        audio_buffer = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.extend(chunk["data"])
        return bytes(audio_buffer)

    async def _hf_tts(self, spoken_text: str) -> bytes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_hf_engine().synthesize, spoken_text)

    async def _gtts(self, spoken_text: str, lang: str) -> bytes:
        gtts_lang = "hi" if lang.startswith("hi") else "en"
        tts = gTTS(text=spoken_text, lang=gtts_lang, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()

    async def generate_speech_async(
        self,
        text: str,
        lang: str = "hi",
        voice: Optional[str] = None,
    ) -> bytes:
        raw_clean = text.strip()
        spoken_text = clean_text_for_speech(raw_clean)
        if not spoken_text:
            spoken_text = raw_clean
        if not spoken_text:
            return b""

        provider = (settings.TTS_PROVIDER or "auto").lower()
        cascade = []

        if provider == "hf":
            cascade = ["hf", "edge", "gtts"]
        elif provider == "edge":
            cascade = ["edge", "hf", "gtts"]
        else:
            cascade = ["edge", "hf", "gtts"]

        for step in cascade:
            try:
                if step == "edge":
                    audio = await self._edge_tts(spoken_text, lang, voice)
                elif step == "hf":
                    audio = await self._hf_tts(spoken_text)
                else:
                    audio = await self._gtts(spoken_text, lang)

                if audio:
                    return audio
            except Exception as exc:
                logger.warning("[TTS] %s failed: %s, trying next...", step, exc)

        return b""

    def generate_speech(self, text: str, lang: str = "hi", voice: Optional[str] = None) -> bytes:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(self.generate_speech_async(text, lang, voice))
        return asyncio.run(self.generate_speech_async(text, lang, voice))

    def generate_speech_base64(self, text: str, lang: str = "hi", voice: Optional[str] = None) -> str:
        audio_bytes = self.generate_speech(text, lang, voice)
        if not audio_bytes:
            return ""

        b64_str = base64.b64encode(audio_bytes).decode("utf-8")
        mime_type = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mp3"
        return f"data:{mime_type};base64,{b64_str}"


tts_service = TTSService()
