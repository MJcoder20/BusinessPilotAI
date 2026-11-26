
import re
from typing import Any

from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import ToolMessage


SUSPICIOUS_PATTERNS = [
    re.compile(
        r"\b(ignore|disregard|override|bypass)\b.{0,100}"
        r"\b(previous|above|prior|system|developer|all|actual)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(reveal|disclose|print|expose|show)\b.{0,100}"
        r"\b(system prompt|internal instructions|api keys?|credentials|secrets)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(system override|developer override|system instruction|"
        r"new instructions|highest priority)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(do not mention|hide the fact|fabricate|invent)\b",
        re.IGNORECASE,
    ),
]

OVERRIDE_HEADING = re.compile(
    r"^\s*(system|developer)\s+override\s*:?\s*$",
    re.IGNORECASE,
)

REDACTED_TEXT = "[suspicious text omitted]"


def is_suspicious_text(value: str) -> bool:
    """Detect common instruction-like content in untrusted text."""
    normalized = " ".join(value.split())

    return any(
        pattern.search(normalized)
        for pattern in SUSPICIOUS_PATTERNS
    )


def sanitize_text(value: str) -> str:
    """
    Sanitize text line by line so legitimate business records survive.

    Explicit override sections are omitted through the end of the
    section. Suspicious field values are replaced while preserving
    their field labels.
    """
    lines = value.splitlines()
    sanitized_lines = []
    inside_override_block = False

    for line in lines:
        if inside_override_block:
            continue

        if OVERRIDE_HEADING.match(line):
            sanitized_lines.append(REDACTED_TEXT)
            inside_override_block = True
            continue

        if not is_suspicious_text(line):
            sanitized_lines.append(line)
            continue

        # Preserve a legitimate field label when its value is suspicious.
        field_match = re.match(
            r"^(\s*[^:\n]{1,80}:\s*)(.*)$",
            line,
        )

        if field_match:
            prefix, _ = field_match.groups()

            if is_suspicious_text(prefix):
                sanitized_lines.append(REDACTED_TEXT)
            else:
                sanitized_lines.append(prefix + REDACTED_TEXT)
        else:
            sanitized_lines.append(REDACTED_TEXT)

    return "\n".join(sanitized_lines)


def sanitize_untrusted_data(value: Any) -> Any:
    """
    Recursively sanitize untrusted tool results.

    Preserve legitimate values, numerical data, and data structures.
    """
    if isinstance(value, str):
        return sanitize_text(value)

    if isinstance(value, dict):
        return {
            key: sanitize_untrusted_data(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            sanitize_untrusted_data(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            sanitize_untrusted_data(item)
            for item in value
        )

    return value


@wrap_tool_call
def sanitize_tool_results(request, handler):
    """Sanitize tool results before they are returned to the model."""
    result = handler(request)

    if isinstance(result, ToolMessage):
        return result.model_copy(
            update={
                "content": sanitize_untrusted_data(result.content)
            }
        )

    return result
