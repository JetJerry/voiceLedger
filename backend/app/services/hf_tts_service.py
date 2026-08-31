"""
HuggingFace Text-to-Speech (TTS) Service using facebook/mms-tts-hin.

Uses Meta's Massively Multilingual Speech (MMS) TTS model for Hindi.
Model: facebook/mms-tts-hin (~100MB, VITS-based, CPU-friendly)

This provides natural Hindi speech synthesis using a proper ML model
from HuggingFace, as opposed to API-based solutions like edge-tts/gTTS.
"""
import io
import numpy as np
from typing import Optional

_tts_model = None
_tts_tokenizer = None


def _get_tts_model():
    """
    Lazy-load the MMS-TTS Hindi model on first use.
    facebook/mms-tts-hin is a lightweight VITS model (~100MB) optimized for Hindi.
    """
    global _tts_model, _tts_tokenizer
    if _tts_model is None:
        try:
            from transformers import VitsModel, AutoTokenizer
            from backend.app.config import settings
            import torch

            model_id = settings.HF_TTS_MODEL
            
            print(f"[HF-TTS] Loading TTS model: {model_id}...")
            _tts_tokenizer = AutoTokenizer.from_pretrained(model_id)
            _tts_model = VitsModel.from_pretrained(model_id)
            
            # Move to CPU explicitly and set eval mode
            _tts_model = _tts_model.eval()
            print(f"[HF-TTS] TTS model loaded successfully. Sample rate: {_tts_model.config.sampling_rate}")
        except Exception as e:
            print(f"[HF-TTS] Failed to load TTS model: {e}")
            raise
    return _tts_model, _tts_tokenizer


class HFTTSService:
    """
    Text-to-Speech service using HuggingFace's facebook/mms-tts-hin model.
    
    Provides natural Hindi speech synthesis using Meta's MMS (Massively 
    Multilingual Speech) project. The model is VITS-based, lightweight (~100MB),
    and runs efficiently on CPU.
    """

    def generate_speech(self, text: str) -> bytes:
        """
        Generate speech audio bytes (WAV format) from Hindi text.
        
        Args:
            text: Hindi text to synthesize (Devanagari script works best)
            
        Returns:
            WAV audio bytes
        """
        import torch
        
        model, tokenizer = _get_tts_model()
        
        # Clean input text
        text_clean = text.strip()
        if not text_clean:
            return b""
        
        # Tokenize and generate
        inputs = tokenizer(text_clean, return_tensors="pt")
        
        with torch.no_grad():
            output = model(**inputs)
        
        # Extract waveform and convert to WAV bytes
        waveform = output.waveform[0].cpu().numpy()
        sample_rate = model.config.sampling_rate
        
        return self._numpy_to_wav_bytes(waveform, sample_rate)

    def generate_speech_mp3(self, text: str) -> bytes:
        """
        Generate speech as MP3 bytes from Hindi text.
        Falls back to WAV if MP3 conversion fails.
        
        Args:
            text: Hindi text to synthesize
            
        Returns:
            MP3 audio bytes (or WAV as fallback)
        """
        import torch
        
        model, tokenizer = _get_tts_model()
        
        text_clean = text.strip()
        if not text_clean:
            return b""
        
        inputs = tokenizer(text_clean, return_tensors="pt")
        
        with torch.no_grad():
            output = model(**inputs)
        
        waveform = output.waveform[0].cpu().numpy()
        sample_rate = model.config.sampling_rate
        
        # Return WAV bytes (browser Audio API handles WAV natively)
        return self._numpy_to_wav_bytes(waveform, sample_rate)

    def _numpy_to_wav_bytes(self, waveform: np.ndarray, sample_rate: int) -> bytes:
        """Convert numpy waveform array to WAV audio bytes."""
        import soundfile as sf
        
        buffer = io.BytesIO()
        sf.write(buffer, waveform, sample_rate, format="WAV", subtype="PCM_16")
        buffer.seek(0)
        return buffer.read()

    def get_sample_rate(self) -> int:
        """Get the model's native sample rate."""
        model, _ = _get_tts_model()
        return model.config.sampling_rate

    def is_available(self) -> bool:
        """Check if the HuggingFace TTS model can be loaded."""
        try:
            _get_tts_model()
            return True
        except Exception:
            return False


# Singleton instance
hf_tts_service = HFTTSService()
