import re
from typing import List, Tuple
from models import GuardrailResult
from observability import record_guardrail
from config import settings

INJECTION_PATTERNS = [
    r"ignore\s+all\s+previous\s+instructions",
    r"reveal\s+the\s+system\s+prompt",
    r"developer\s+mode",
    r"you\s+are\s+now\+dan",
]

ILLEGAL_TOPICS = [
    "visa fraud", "fake passport", "smuggling", "weapons", "buy drugs"
]

PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
}

def redact_pii(text: str) -> Tuple[str, List[str]]:
    redacted = text
    hits = []
    for name, pat in PII_PATTERNS.items():
        if pat.search(redacted):
            hits.append(name)
            redacted = pat.sub(f"[REDACTED_{name.upper()}]", redacted)
    return redacted, hits

def run_input_guardrails(user_text: str) -> Tuple[str, List[GuardrailResult], bool]:
    results: List[GuardrailResult] = []

    if len(user_text) > 4000:
        name = "input.size_limit"
        reason = "Please shorten your input and try again."
        record_guardrail(name, "input", "block", reason, length=len(user_text))
        results.append(GuardrailResult(name=name, stage="input", action="block", reason=reason))
        return user_text, results, True

    if settings.ENABLE_INJECTION_DETECTION:
        for pat in INJECTION_PATTERNS:
            # The incoming text is a tuple, since it is a JSON from the front end. Join this to make a string
            regex_safe_user_text = ' '.join(user_text)
            if re.search(pat, regex_safe_user_text, re.IGNORECASE):
                name = "input.prompt_injection"
                reason = "Prompt injection input detected"
                record_guardrail(name, "input", "block", reason, pattern=pat)
                results.append(GuardrailResult(name=name, stage="input", action="block", reason=reason, meta={"pattern": pat}))
                return user_text, results, True

    if settings.ENABLE_TOPIC_GATING:
        lowered = regex_safe_user_text.lower()
        for topic in ILLEGAL_TOPICS:
            if topic in lowered:
                name = "input.illegal_topic"
                reason = f"Request includes disallowed topic: {topic}"
                record_guardrail(name, "input", "block", reason, topic=topic)
                results.append(GuardrailResult(name=name, stage="input", action="block", reason=reason, meta={"topic": topic}))
                return user_text, results, True

    if settings.ENABLE_PII_REDACTION:
        redacted, hits = redact_pii(regex_safe_user_text)
        if hits:
            pii = ",".join(hits)
            name = "input.pii_redaction"
            reason = f"Redacted PII Types: {pii}"
            record_guardrail(name, "input", "redact", reason, pii=pii)
            results.append(GuardrailResult(name=name, stage="input", action="redact", reason=reason, meta={"types": pii}))
    return user_text, results, False

def run_output_guardrails(output_text: str) -> Tuple[List[GuardrailResult], bool, str]:
    results: List[GuardrailResult] = []

    unsafe = ["fake passport", "smuggle", "weapons", "buy illegal"]
    if settings.ENABLE_OUTPUT_VALIDATION:
        for kw in unsafe:
            if kw in output_text.lower():
                name = "output.unsafe_content"
                reason = "Model output contains unsafe content"
                record_guardrail(name, "output", "block", reason, keyword=kw)
                results.append(GuardrailResult(name=name, stage="output", action="block", reason=reason, meta={"keyword": kw}))
                return results, True, output_text

    sensitive = ["visa", "entry requirements", "customs", "border control"]
    if any(s in output_text.lower() for s in sensitive):
        name = "output.travel.disclaimer"
        reason = "Added disclaimer for visa/entry requirement information"
        record_guardrail(name, "output", "warn", reason)
        results.append(GuardrailResult(name=name, stage="output", action="warn", reason=reason))
        output_text += "\n\n> Note: Visa/ entry requirements can change. Please verify via official sources. \n"
    return results, False, output_text

