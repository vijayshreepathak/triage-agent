"""Hardcoded safety constants.

The disclaimer is a *constant*, not a prompt output. If the LLM were asked
to produce it, a bad sample could drop or soften it — unacceptable for a
clinical product. The response builder appends these verbatim on every
single response, including error responses.
"""

from __future__ import annotations

from typing import Final

from app.models.enums import UrgencyLevel

DISCLAIMERS: Final[tuple[str, ...]] = (
    "This is an AI-generated triage suggestion only.",
    "Not a diagnosis. Seek professional medical advice.",
    "If symptoms worsen or you are in doubt, seek emergency medical help immediately.",
)

NO_VERIFIED_SOURCE_MESSAGE: Final[str] = "No verified external source found."

EMERGENCY_ACTION: Final[str] = "Call emergency services (911 / 112 / 999) right now or go to the nearest ER."
HIGH_ACTION: Final[str] = "Seek urgent medical care today — urgent care centre or same-day GP/ER assessment."
MODERATE_ACTION: Final[str] = (
    "Book an appointment with a doctor within the next few days. Monitor for worsening."
)
LOW_ACTION: Final[str] = "Self-care is reasonable. See a doctor if symptoms persist or worsen."

# Deterministic urgency -> action mapping used by the response builder.
ACTION_BY_URGENCY: Final[dict[UrgencyLevel, str]] = {
    UrgencyLevel.EMERGENCY: EMERGENCY_ACTION,
    UrgencyLevel.HIGH: HIGH_ACTION,
    UrgencyLevel.MODERATE: MODERATE_ACTION,
    UrgencyLevel.LOW: LOW_ACTION,
}

# Fallback text used when the explanation node fails after all retries.
SAFE_FALLBACK_REASONING: Final[str] = (
    "An automated explanation could not be generated for this request. "
    "The urgency level above was determined from detected symptoms and safety rules. "
    "When in doubt, seek medical care."
)
