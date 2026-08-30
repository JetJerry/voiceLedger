import io
import asyncio
import base64
from typing import Optional, Tuple
import edge_tts
from gtts import gTTS


# Neural voice constants for natural Indian languages
VOICE_HINDI = "hi-IN-MadhurNeural"       # Natural Hindi Male
VOICE_HINDI_FEMALE = "hi-IN-SwaraNeural" # Natural Hindi Female
VOICE_ENGLISH_INDIAN = "en-IN-PrabhatNeural" # Indian English Male
VOICE_ENGLISH_FEMALE = "en-IN-NeerjaNeural"  # Indian English Female


class TTSService:
    """
    Text-to-Speech (TTS) and Hindi-to-English / Hindi-to-Hindi Voice Synthesis Service.
    Uses Edge-TTS Neural models and gTTS fallback.
    """

    async def generate_speech_async(
        self,
        text: str,
        lang: str = "hi",
        voice: Optional[str] = None
    ) -> bytes:
        """
        Synthesizes natural speech audio for Hindi (hi) or English (en).
        Returns raw MP3 audio bytes.
        """
        text_clean = text.strip()
        if not text_clean:
            return b""

        # Select neural voice
        selected_voice = voice
        if not selected_voice:
            if lang.startswith("hi"):
                selected_voice = VOICE_HINDI
            else:
                selected_voice = VOICE_ENGLISH_INDIAN

        # 1. Primary: Edge-TTS Neural Voice Model
        try:
            communicate = edge_tts.Communicate(text_clean, selected_voice)
            audio_buffer = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.extend(chunk["data"])
            if audio_buffer:
                return bytes(audio_buffer)
        except Exception as e:
            print(f"Edge-TTS synthesis error, using gTTS fallback: {e}")

        # 2. Fallback: gTTS (Google Text-To-Speech)
        try:
            gtts_lang = "hi" if lang.startswith("hi") else "en"
            tts = gTTS(text=text_clean, lang=gtts_lang, slow=False)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            return fp.read()
        except Exception as e:
            print(f"gTTS fallback failed: {e}")
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
        Returns speech audio encoded as a base64 Data URL (ready for <audio src="..."> playback in browser).
        """
        audio_bytes = self.generate_speech(text, lang, voice)
        if not audio_bytes:
            return ""
        b64_str = base64.b64encode(audio_bytes).decode("utf-8")
        return f"data:audio/mp3;base64,{b64_str}"


tts_service = TTSService()
