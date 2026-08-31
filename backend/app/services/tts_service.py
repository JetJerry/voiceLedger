"""
Text-to-Speech (TTS) Service — Multi-Provider with HuggingFace Model Priority.

TTS Provider Cascade:
1. PRIMARY:   HuggingFace facebook/mms-tts-hin (local ML model, Hindi neural voice)
2. FALLBACK1: Edge-TTS (Microsoft Neural voices via network API)
3. FALLBACK2: gTTS (Google Text-To-Speech via network API)

The HuggingFace model runs fully offline after first download.
Edge-TTS and gTTS require network access.
"""
import io
import asyncio
import base64
from typing import Optional
import edge_tts
from gtts import gTTS


# Neural voice constants for Edge-TTS fallback
VOICE_HINDI = "hi-IN-MadhurNeural"           # Natural Hindi Male
VOICE_HINDI_FEMALE = "hi-IN-SwaraNeural"      # Natural Hindi Female
VOICE_ENGLISH_INDIAN = "en-IN-PrabhatNeural"  # Indian English Male
VOICE_ENGLISH_FEMALE = "en-IN-NeerjaNeural"   # Indian English Female


class TTSService:
    """
    Multi-provider Text-to-Speech Service with HuggingFace model priority.

    Provider cascade:
    1. HuggingFace MMS-TTS (facebook/mms-tts-hin) — local ML model
    2. Edge-TTS Neural models — Microsoft network API
    3. gTTS — Google network API fallback
    """

    def __init__(self):
        self._hf_tts = None
        self._hf_available = None  # None = not checked yet

    def _get_hf_tts(self):
        """Lazy-load the HuggingFace TTS service."""
        if self._hf_available is None:
            try:
                from backend.app.services.hf_tts_service import hf_tts_service
                self._hf_tts = hf_tts_service
                # Test if model can be loaded (lazy — actual load on first call)
                self._hf_available = True
                print("[TTS] HuggingFace MMS-TTS (facebook/mms-tts-hin) available as primary TTS.")
            except Exception as e:
                print(f"[TTS] HuggingFace TTS not available, will use Edge-TTS: {e}")
                self._hf_available = False
        return self._hf_tts if self._hf_available else None

    async def generate_speech_async(
        self,
        text: str,
        lang: str = "hi",
        voice: Optional[str] = None
    ) -> bytes:
        """
        Synthesizes natural speech audio for Hindi (hi) or English (en).
        Returns raw audio bytes (WAV from HuggingFace, MP3 from Edge-TTS/gTTS).
        
        Provider cascade: HuggingFace → Edge-TTS → gTTS
        """
        text_clean = text.strip()
        if not text_clean:
            return b""

        # 1. PRIMARY: HuggingFace MMS-TTS (facebook/mms-tts-hin)
        if lang.startswith("hi"):
            hf_tts = self._get_hf_tts()
            if hf_tts:
                try:
                    audio_bytes = hf_tts.generate_speech(text_clean)
                    if audio_bytes:
                        print(f"[TTS] Generated speech via HuggingFace MMS-TTS ({len(audio_bytes)} bytes)")
                        return audio_bytes
                except Exception as e:
                    print(f"[TTS] HuggingFace TTS failed, falling back to Edge-TTS: {e}")

        # 2. FALLBACK 1: Edge-TTS Neural Voice Model
        selected_voice = voice
        if not selected_voice:
            if lang.startswith("hi"):
                selected_voice = VOICE_HINDI
            else:
                selected_voice = VOICE_ENGLISH_INDIAN

        try:
            communicate = edge_tts.Communicate(text_clean, selected_voice)
            audio_buffer = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.extend(chunk["data"])
            if audio_buffer:
                print(f"[TTS] Generated speech via Edge-TTS ({len(audio_buffer)} bytes)")
                return bytes(audio_buffer)
        except Exception as e:
            print(f"[TTS] Edge-TTS synthesis error, using gTTS fallback: {e}")

        # 3. FALLBACK 2: gTTS (Google Text-To-Speech)
        try:
            gtts_lang = "hi" if lang.startswith("hi") else "en"
            tts = gTTS(text=text_clean, lang=gtts_lang, slow=False)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            audio_bytes = fp.read()
            print(f"[TTS] Generated speech via gTTS ({len(audio_bytes)} bytes)")
            return audio_bytes
        except Exception as e:
            print(f"[TTS] gTTS fallback also failed: {e}")
            return b""

    def generate_speech(self, text: str, lang: str = "hi", voice: Optional[str] = None) -> bytes:
        """
        Synchronous wrapper for speech synthesis.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(self.generate_speech_async(text, lang, voice))
        else:
            return asyncio.run(self.generate_speech_async(text, lang, voice))

    def generate_speech_base64(self, text: str, lang: str = "hi", voice: Optional[str] = None) -> str:
        """
        Returns speech audio encoded as a base64 Data URL 
        (ready for <audio src="..."> playback in browser).
        
        Automatically detects audio format (WAV from HuggingFace, MP3 from Edge-TTS/gTTS).
        """
        audio_bytes = self.generate_speech(text, lang, voice)
        if not audio_bytes:
            return ""
        
        b64_str = base64.b64encode(audio_bytes).decode("utf-8")
        
        # Detect format from WAV header magic bytes
        if audio_bytes[:4] == b'RIFF':
            mime_type = "audio/wav"
        else:
            mime_type = "audio/mp3"
        
        return f"data:{mime_type};base64,{b64_str}"


tts_service = TTSService()
