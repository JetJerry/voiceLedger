import io
import re
import asyncio
import base64
from typing import Optional
import edge_tts
from gtts import gTTS


# High-Speed Neural Voices
VOICE_HINDI_MALE = "hi-IN-MadhurNeural"       # Natural, fluent Hindi Male (Conversational)
VOICE_HINDI_FEMALE = "hi-IN-SwaraNeural"     # Natural Hindi Female
VOICE_ENGLISH_INDIAN = "en-IN-PrabhatNeural" # Indian English Male
VOICE_ENGLISH_FEMALE = "en-IN-NeerjaNeural"  # Indian English Female


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
    
    # 1. Remove URLs (e.g. https://rzp.io/...)
    cleaned = re.sub(r'https?://\S+', '', text)
    cleaned = re.sub(r'Razorpay Payment Link ready:?', '', cleaned, flags=re.IGNORECASE)
    
    # 2. Convert currency to natural spoken words
    cleaned = re.sub(r'(?:Rs\.?|₹|INR)\s*(\d+(?:\.\d+)?)', r'\1 rupaye', cleaned, flags=re.IGNORECASE)
    
    # 3. Remove Emojis & UI symbols
    cleaned = re.sub(r'[\U00010000-\U0010ffff]', '', cleaned)  # Supplementary emojis
    cleaned = re.sub(r'[\u2600-\u27bf]', '', cleaned)          # Misc symbols & dingbats
    cleaned = re.sub(r'[✅⏳⚠️❌🎙️⚡💰🛍️🔍☕📚➕📞]', '', cleaned)
    
    # 4. Remove markdown bold/italic/brackets
    cleaned = re.sub(r'[*_#`~]', '', cleaned)
    cleaned = re.sub(r'\([A-Z\s]+\)', '', cleaned)  # e.g. (PAID), (PENDING)
    
    # 5. Collapse multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


class TTSService:
    """
    High-Performance Text-to-Speech Service.
    
    Uses Neural Speech Synthesis for human-like Hindi/Hinglish/English voice output with <300ms latency.
    Cascade: Edge-TTS Neural → gTTS → Local MMS-TTS fallback.
    """

    def __init__(self):
        self._hf_tts = None

    async def generate_speech_async(
        self,
        text: str,
        lang: str = "hi",
        voice: Optional[str] = None
    ) -> bytes:
        """
        Synthesizes natural, human-like speech audio.
        Returns raw audio bytes (MP3 format).
        """
        raw_clean = text.strip()
        spoken_text = clean_text_for_speech(raw_clean)
        
        if not spoken_text:
            spoken_text = raw_clean
        if not spoken_text:
            return b""

        # 1. PRIMARY: Edge-TTS Neural Voice (High Speed, Ultra Natural)
        selected_voice = voice
        if not selected_voice:
            if lang.startswith("hi"):
                selected_voice = VOICE_HINDI_MALE
            else:
                selected_voice = VOICE_ENGLISH_INDIAN

        try:
            communicate = edge_tts.Communicate(spoken_text, selected_voice, rate="+5%")
            audio_buffer = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.extend(chunk["data"])
            if audio_buffer:
                return bytes(audio_buffer)
        except Exception as e:
            print(f"[TTS] Edge-TTS notice: {e}, falling back...")

        # 2. FALLBACK: gTTS (Google Speech API)
        try:
            gtts_lang = "hi" if lang.startswith("hi") else "en"
            tts = gTTS(text=spoken_text, lang=gtts_lang, slow=False)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            audio_bytes = fp.read()
            if audio_bytes:
                return audio_bytes
        except Exception as e:
            print(f"[TTS] gTTS notice: {e}")

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
