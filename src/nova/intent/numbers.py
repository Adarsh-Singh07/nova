"""Natural language number and duration parsing for NOVA intent engine.

Converts spoken English numbers (e.g. "twenty five", "seventy", "one hundred")
and durations (e.g. "twenty five minutes", "half an hour", "two and a half minutes")
into typed numeric primitives.
"""

from __future__ import annotations

import re

# Word to number mappings
UNITS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

TENS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

SCALES: dict[str, int] = {
    "hundred": 100,
    "thousand": 1000,
}


def parse_number(text: str) -> int | None:
    """Parse a spoken or written number from natural language text.

    Examples:
        >>> parse_number("50")
        50
        >>> parse_number("twenty five")
        25
        >>> parse_number("seventy percent")
        70
        >>> parse_number("one hundred")
        100
        >>> parse_number("invalid")
        None
    """
    clean = text.lower().strip()
    # Remove common filler words and percentage signs
    clean = clean.replace("%", "").replace("percent", "").strip()

    # Direct digit match
    digit_match = re.search(r"\b\d+\b", clean)
    if digit_match:
        try:
            return int(digit_match.group(0))
        except ValueError:
            pass

    # Word numeral parsing
    tokens = clean.split()
    total = 0
    current = 0
    matched_any = False

    for token in tokens:
        token = token.strip(",.-")
        if token in ("and", "to", "the"):
            continue

        if token in UNITS:
            current += UNITS[token]
            matched_any = True
        elif token in TENS:
            current += TENS[token]
            matched_any = True
        elif token in SCALES:
            scale = SCALES[token]
            current = (current if current != 0 else 1) * scale
            total += current
            current = 0
            matched_any = True

    if matched_any:
        return total + current

    return None


def parse_duration(text: str) -> float | None:
    """Parse spoken duration into total seconds.

    Supports:
        - "half an hour" -> 1800.0
        - "an hour" -> 3600.0
        - "two and a half minutes" -> 150.0
        - "10 minutes" -> 600.0
        - "twenty five minutes" -> 1500.0
        - "5 minutes and 30 seconds" -> 330.0
        - "45 seconds" -> 45.0
        - "one hour and fifteen minutes" -> 4500.0
    """
    clean = text.lower().strip()

    # Common colloquial fractions
    if "half an hour" in clean:
        return 1800.0
    if "an hour" in clean or "one hour" in clean:
        base_hour = 3600.0
        # Check if there are extra minutes appended
        extra_match = re.search(r"(?:and\s+)?(\d+|[\w\s]+)\s+minutes?", clean)
        if extra_match and "half" not in extra_match.group(1):
            extra_num = parse_number(extra_match.group(1))
            if extra_num:
                return base_hour + (extra_num * 60.0)
        return base_hour

    if "two and a half minutes" in clean:
        return 150.0
    if "one and a half minutes" in clean:
        return 90.0

    total_seconds = 0.0
    found_any = False

    # Hours match: require full word or hrs
    hour_match = re.search(r"(\d+|[\w\s]+?)\s*(?:hours?|hrs?)\b", clean)
    if hour_match:
        val = parse_number(hour_match.group(1))
        if val is not None:
            total_seconds += val * 3600.0
            found_any = True
            clean = clean[hour_match.end() :]

    # Minutes match: require full word or mins
    min_match = re.search(r"(\d+|[\w\s]+?)\s*(?:minutes?|mins?)\b", clean)
    if min_match:
        val = parse_number(min_match.group(1))
        if val is not None:
            total_seconds += val * 60.0
            found_any = True
            clean = clean[min_match.end() :]

    # Seconds match: require full word or secs
    sec_match = re.search(r"(\d+|[\w\s]+?)\s*(?:seconds?|secs?)\b", clean)
    if sec_match:
        val = parse_number(sec_match.group(1))
        if val is not None:
            total_seconds += float(val)
            found_any = True

    if found_any and total_seconds > 0:
        return total_seconds

    # Fallback: if only a number was provided without unit, or "timer for X"
    fallback_num = parse_number(clean)
    if fallback_num is not None and fallback_num > 0:
        # Default to seconds if under 60, else minutes?
        # Standard convention for voice timer when unit is omitted is minutes
        return float(fallback_num * 60)

    return None
