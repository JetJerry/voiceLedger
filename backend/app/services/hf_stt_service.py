"""
HuggingFace Speech-to-Text (STT) Service using faster-whisper.

Uses the OpenAI Whisper model (via CTranslate2) for efficient, 
server-side Hindi/Hinglish speech recognition.
Model: openai/whisper-small (CPU int8 quantized for fast inference)
"""
import io
import os
import tempfile
from typing import Optional, Tuple

_whisper_model = None


def _get_whisper_model():
    """
    Lazy-load the Whisper model on first use.
    Supports CUDA GPU (perfect for 4GB VRAM graphics) with automatic CPU fallback.
    """
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        from backend.app.config import settings
        import torch

        model_size = settings.WHISPER_MODEL_SIZE or "small"
        configured_device = settings.WHISPER_DEVICE
        
        # If set to cuda or auto, check if CUDA is actually available
        if configured_device == "cuda" or (configured_device == "auto" and torch.cuda.is_available()):
            try:
                print(f"[HF-STT] Attempting CUDA GPU loading for Whisper ({model_size})...")
                _whisper_model = WhisperModel(
                    model_size,
                    device="cuda",
                    compute_type="float16" if torch.cuda.is_available() else "int8",
                )
                print(f"[HF-STT] Whisper loaded successfully on CUDA GPU (VRAM optimized).")
                return _whisper_model
            except Exception as cuda_err:
                print(f"[HF-STT] CUDA load failed ({cuda_err}), falling back to CPU...")

        # CPU fallback (int8 quantized, lightweight & fast)
        try:
            print(f"[HF-STT] Loading Whisper model on CPU: {model_size} (int8)...")
            _whisper_model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
            )
            print(f"[HF-STT] Whisper model loaded successfully on CPU.")
        except Exception as e:
            print(f"[HF-STT] Failed to load Whisper model: {e}")
            raise
    return _whisper_model


class HFSTTService:
    """
    Server-side Speech-to-Text service using HuggingFace's Whisper model
    via faster-whisper (CTranslate2 backend) for efficient CPU inference.
    
    Supports Hindi, Hinglish, and English transcription from raw audio bytes.
    """

    def transcribe_audio_bytes(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/webm",
        language: str = "hi",
    ) -> Tuple[str, float, str]:
        """
        Transcribe raw audio bytes to text using Whisper.
        
        Args:
            audio_bytes: Raw audio data (webm, wav, mp3, etc.)
            mime_type: MIME type of the audio
            language: Language code ('hi' for Hindi, 'en' for English, None for auto-detect)
            
        Returns:
            Tuple of (transcribed_text, language_probability, detected_language)
        """
        # Determine file extension from mime type
        ext_map = {
            "audio/webm": ".webm",
            "audio/wav": ".wav",
            "audio/wave": ".wav",
            "audio/x-wav": ".wav",
            "audio/mp3": ".mp3",
            "audio/mpeg": ".mp3",
            "audio/ogg": ".ogg",
            "audio/flac": ".flac",
            "audio/m4a": ".m4a",
            "audio/mp4": ".mp4",
        }
        extension = ext_map.get(mime_type, ".webm")
        
        # Write audio bytes to a temporary file (faster-whisper needs a file path)
        tmp_file = None
        try:
            tmp_file = tempfile.NamedTemporaryFile(
                suffix=extension, delete=False, prefix="vl_stt_"
            )
            tmp_file.write(audio_bytes)
            tmp_file.flush()
            tmp_file.close()
            
            return self.transcribe_file(tmp_file.name, language=language)
        finally:
            # Clean up temp file
            if tmp_file and os.path.exists(tmp_file.name):
                try:
                    os.unlink(tmp_file.name)
                except OSError:
                    pass

    def transcribe_file(
        self,
        file_path: str,
        language: Optional[str] = "hi",
    ) -> Tuple[str, float, str]:
        """
        Transcribe an audio file to text using Whisper.
        
        Args:
            file_path: Path to the audio file
            language: Language hint ('hi', 'en', or None for auto-detect)
            
        Returns:
            Tuple of (transcribed_text, language_probability, detected_language)
        """
        model = _get_whisper_model()
        
        # Transcribe with language hint
        segments, info = model.transcribe(
            file_path,
            language=language,
            beam_size=5,
            best_of=3,
            vad_filter=True,  # Filter out silence for faster processing
        )
        
        # Collect all segment texts
        full_text = " ".join(segment.text.strip() for segment in segments)
        
        return (
            full_text.strip(),
            info.language_probability,
            info.language,
        )

    def is_available(self) -> bool:
        """Check if the Whisper model can be loaded."""
        try:
            _get_whisper_model()
            return True
        except Exception:
            return False


# Singleton instance
hf_stt_service = HFSTTService()
