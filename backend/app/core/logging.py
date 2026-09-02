import contextvars
import logging
import re
from typing import Optional

# Context variable for request tracing
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# Sensitive patterns that should be masked in log output
SENSITIVE_PATTERNS = [
    (re.compile(r'(["\']?(?:password|passwd|secret|jwt|token|access_token|refresh_token|signature|api_key|webhook_secret)["\']?\s*[:=]\s*["\'])([^"\']+)["\']', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(Bearer\s+)[A-Za-z0-9\-_.]+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(rzp_(?:test|live)_[A-Za-z0-9]+)', re.IGNORECASE), r'[REDACTED_RZP_KEY]'),
]


def sanitize_log_message(message: str) -> str:
    """Sanitize log messages by masking sensitive tokens, passwords, and secrets."""
    if not isinstance(message, str):
        return message
    sanitized = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class RequestIdFilter(logging.Filter):
    """Log filter that injects the current request_id into the log record."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        if isinstance(record.msg, str):
            record.msg = sanitize_log_message(record.msg)
        return True


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure structured logging for VoiceLedger."""
    logger = logging.getLogger("voiceledger")
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (request_id=%(request_id)s): %(message)s"
        )
        handler.setFormatter(formatter)
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)

    logger.propagate = False
    return logger


logger = setup_logging()
