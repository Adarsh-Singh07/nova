"""Safe compound command splitting for NOVA intent engine.

Enforces the invariant: A phrase is split if and only if BOTH halves independently
parse as valid, allowlisted commands. Otherwise, the phrase remains a single command turn.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nova.core.interfaces import ActionRequest

# Conjunction delimiters to check in order of priority
CONJUNCTIONS: list[str] = [" and ", " then ", " & "]


def split_compound_commands(
    text: str,
    parser_fn: Callable[[str], ActionRequest | None],
) -> list[str]:
    """Split natural language input into multiple atomic command turns.

    Rules:
    - Only splits if BOTH segments independently parse to valid ActionRequests via parser_fn.
    - If either segment fails to parse, text is preserved as a single command turn.
    - Recursively processes multi-part commands (e.g. "cmd1 and cmd2 then cmd3").

    Examples:
        - "pause the music and open slack" -> ["pause the music", "open slack"]
        - "search salt and pepper" -> ["search salt and pepper"]
        - "play rock and roll" -> ["play rock and roll"]
        - "open notes and reminders" -> ["open notes and reminders"]
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    for conj in CONJUNCTIONS:
        if conj not in clean_text.lower():
            continue

        # Find occurrence of conjunction (case-insensitive)
        lower_text = clean_text.lower()
        start_idx = 0
        while True:
            idx = lower_text.find(conj, start_idx)
            if idx == -1:
                break

            left_part = clean_text[:idx].strip()
            right_part = clean_text[idx + len(conj) :].strip()

            if left_part and right_part:
                left_req = parser_fn(left_part)
                right_req = parser_fn(right_part)

                if left_req is not None and right_req is not None:
                    # Both sides are valid commands!
                    # Recursively check right side in case of 3+ compound commands
                    sub_splits = split_compound_commands(right_part, parser_fn)
                    return [left_part, *sub_splits]

            start_idx = idx + len(conj)

    return [clean_text]
