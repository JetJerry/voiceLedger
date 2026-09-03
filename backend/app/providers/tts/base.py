"""
VoiceLedger TTS Provider Abstraction.

Defines the vendor-neutral Text-to-Speech interface and audio artifact models.
The rest of VoiceLedger depends exclusively on this abstraction rather than
concrete vendor SDKs.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AudioResult:
    """Standardized synthesized audio artifact."""
    audio_bytes: bytes
    content_type: str  # e.g. "audio/wav", "audio/mpeg"
    duration_seconds: Optional[float] = None

    def __repr__(self) -> str:
        return (
            f"<AudioResult size={len(self.audio_bytes)} bytes "
            f"type='{self.content_type}' duration={self.duration_seconds}>"
        )


class TTSProvider(ABC):
    """Abstract interface for voice audio synthesis providers."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        language: str = "en-IN",
        voice: Optional[str] = None,
    ) -> AudioResult:
        """
        Synthesize speech audio from plain text.

        :param text: Spoken notification message.
        :param language: IETF BCP 47 language code (e.g. 'en-IN', 'hi-IN').
        :param voice: Optional vendor-specific voice identifier.
        :return: AudioResult containing raw audio bytes and MIME content type.
        """
        pass
