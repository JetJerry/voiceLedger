"""
Deterministic Mock TTS Provider for VoiceLedger.

Provides fast, network-independent, reliable speech synthesis for local environments
and automated testing suites.
"""
import hashlib
import io
import struct
from typing import Optional

from backend.app.providers.tts.base import TTSProvider, AudioResult


class MockTTSProvider(TTSProvider):
    """
    Deterministic in-memory speech synthesizer.
    Generates standard valid PCM WAV audio headers with deterministic sample data.
    """

    def __init__(self, simulate_failure: bool = False):
        self.simulate_failure = simulate_failure

    async def synthesize(
        self,
        text: str,
        language: str = "en-IN",
        voice: Optional[str] = None,
    ) -> AudioResult:
        if self.simulate_failure:
            raise RuntimeError("Simulated TTS synthesis provider failure")

        if not text or not text.strip():
            raise ValueError("Cannot synthesize empty text")

        # Create a valid minimal PCM WAV audio file (16kHz, 16-bit mono)
        sample_rate = 16000
        num_channels = 1
        bytes_per_sample = 2
        # Deterministic duration based on word count (approx 0.3s per word, minimum 1.0s)
        word_count = len(text.split())
        duration = max(1.0, word_count * 0.35)
        num_samples = int(sample_rate * duration)
        data_size = num_samples * num_channels * bytes_per_sample

        buf = io.BytesIO()
        # RIFF header
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + data_size))
        buf.write(b"WAVE")
        # fmt chunk
        buf.write(b"fmt ")
        buf.write(struct.pack("<I", 16))  # Chunk size
        buf.write(struct.pack("<H", 1))   # Audio format (1 = PCM)
        buf.write(struct.pack("<H", num_channels))
        buf.write(struct.pack("<I", sample_rate))
        buf.write(struct.pack("<I", sample_rate * num_channels * bytes_per_sample))  # Byte rate
        buf.write(struct.pack("<H", num_channels * bytes_per_sample))  # Block align
        buf.write(struct.pack("<H", 16))  # Bits per sample
        # data chunk
        buf.write(b"data")
        buf.write(struct.pack("<I", data_size))

        # Generate deterministic synthetic tone samples
        seed = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)
        freq = 440 + (seed % 200)
        import math
        for i in range(num_samples):
            sample = int(3000 * math.sin(2 * math.pi * freq * (i / sample_rate)))
            buf.write(struct.pack("<h", sample))

        buf.seek(0)
        audio_bytes = buf.read()

        return AudioResult(
            audio_bytes=audio_bytes,
            content_type="audio/wav",
            duration_seconds=round(duration, 2),
        )
