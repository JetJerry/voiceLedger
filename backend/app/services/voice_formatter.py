"""
VoiceLedger Deterministic Phrase & Currency Formatter.

Converts canonical financial payment events and minor units into natural,
deterministic verbal speech phrases for physical Soundbox playback.

Invariants:
1. Integer Minor Units: Operates exclusively on amount_minor; rejects floating point.
2. Deterministic & Provable: No LLM/AI dependencies; uses algorithmic number-to-words.
3. Negative Amount Protection: Rejects negative amounts with ValueError.
4. Multilingual Readiness: Supports English (en-IN) and Hindi (hi-IN).
5. Unsupported Event Filtering: Returns None for non-notifiable events (created, failed).
"""
from typing import Optional

_UNITS_EN = (
    "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen"
)

_TENS_EN = (
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"
)

_HINDI_NUMBERS = {
    0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पाँच", 6: "छह", 7: "सात", 8: "आठ", 9: "नौ",
    10: "दस", 20: "बीस", 25: "पच्चीस", 50: "पचास", 100: "एक सौ", 500: "पाँच सौ", 1000: "एक हज़ार",
    1500: "एक हज़ार पाँच सौ", 25000: "पच्चीस हज़ार"
}


def _integer_to_words_en(n: int) -> str:
    """Convert a positive integer into standard English words."""
    if n == 0:
        return "zero"

    parts = []

    # Crores (10,000,000)
    if n >= 10000000:
        crores = n // 10000000
        parts.append(f"{_integer_to_words_en(crores)} crore")
        n %= 10000000

    # Lakhs (100,000)
    if n >= 100000:
        lakhs = n // 100000
        parts.append(f"{_integer_to_words_en(lakhs)} lakh")
        n %= 100000

    # Thousands (1,000)
    if n >= 1000:
        thousands = n // 1000
        parts.append(f"{_integer_to_words_en(thousands)} thousand")
        n %= 1000

    # Hundreds (100)
    if n >= 100:
        hundreds = n // 100
        parts.append(f"{_UNITS_EN[hundreds]} hundred")
        n %= 100

    # Tens and Units
    if n >= 20:
        ten_str = _TENS_EN[n // 10]
        unit_str = _UNITS_EN[n % 10]
        parts.append(f"{ten_str} {unit_str}".strip())
    elif n > 0:
        parts.append(_UNITS_EN[n])

    return " ".join(parts)


def format_amount_in_words(
    amount_minor: int,
    currency: str = "INR",
    language: str = "en-IN",
) -> str:
    """
    Format amount_minor into spoken currency words.

    :param amount_minor: Integer minor units (e.g. 5000 = ₹50.00).
    :param currency: Three-letter ISO currency code (default: INR).
    :param language: Language tag ('en-IN', 'hi-IN').
    :return: Spoken amount string.
    :raises ValueError: If amount_minor is negative or not an integer.
    """
    if not isinstance(amount_minor, int):
        raise ValueError(f"amount_minor must be an integer, received: {type(amount_minor).__name__}")

    if amount_minor < 0:
        raise ValueError("Amount cannot be negative")

    rupees = amount_minor // 100
    paise = amount_minor % 100

    lang = (language or "en-IN").lower()

    if lang.startswith("hi"):
        # Hindi formatting
        num_str = _HINDI_NUMBERS.get(rupees, str(rupees))
        if paise > 0:
            return f"{num_str} रुपये और {paise} पैसे"
        return f"{num_str} रुपये"

    # Default English (en-IN)
    if rupees == 0 and paise == 0:
        return "Zero rupees"

    parts = []
    if rupees > 0:
        rupee_words = _integer_to_words_en(rupees)
        unit = "rupee" if rupees == 1 else "rupees"
        parts.append(f"{rupee_words} {unit}")

    if paise > 0:
        paise_words = _integer_to_words_en(paise)
        unit = "paisa" if paise == 1 else "paise"
        if parts:
            parts.append(f"and {paise_words} {unit}")
        else:
            parts.append(f"{paise_words} {unit}")

    return " ".join(parts).capitalize()


def format_voice_phrase(
    event_type: str,
    amount_minor: int,
    currency: str = "INR",
    language: str = "en-IN",
) -> Optional[str]:
    """
    Generate the complete speech phrase for a financial lifecycle event.

    :param event_type: Canonical event identifier (e.g. 'payment.captured').
    :param amount_minor: Integer minor units.
    :param currency: Three-letter ISO currency code.
    :param language: Language code.
    :return: Full spoken sentence, or None if the event type should not be announced.
    """
    # Filter non-voice events
    notifiable_events = {
        "payment.captured": ("received", "प्राप्त हुए"),
        "payment.authorized": ("received", "प्राप्त हुए"),
        "payment.refunded": ("refunded", "वापस किए गए"),
        "payment.partially_refunded": ("partially refunded", "आंशिक रूप से वापस किए गए"),
    }

    if event_type not in notifiable_events:
        return None

    amount_text = format_amount_in_words(amount_minor, currency=currency, language=language)
    lang = (language or "en-IN").lower()

    en_action, hi_action = notifiable_events[event_type]

    if lang.startswith("hi"):
        return f"{amount_text} {hi_action}"
    else:
        return f"{amount_text} {en_action}"
