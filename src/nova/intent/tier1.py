"""Deterministic Tier 1 Offline Intent Engine for NOVA.

Complies with:
- Rule R5: Strict Allowlist validation, zero arbitrary code execution.
- High-confidence gate for destructive actions (>= 0.85).
- Negation filtering ("don't lock", "do not mute").
- Non-command colloquial expression filtering ("I locked my keys", "play it by ear").
- Registry-only app resolution with RapidFuzz and ambiguity margin.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from nova.core.actions import ALLOWED_KEYBOARD_KEYS, ActionID, AllowlistValidator
from nova.core.interfaces import ActionRequest, IntentEngineProtocol
from nova.core.settings import NovaSettings
from nova.intent.apps import DEFAULT_REGISTERED_APPS, AppRegistry
from nova.intent.compound import split_compound_commands
from nova.intent.numbers import parse_duration, parse_number

logger = logging.getLogger(__name__)

# Leading wake words and politeness prefixes to strip
LEADING_FILLERS_REGEX = re.compile(
    r"^(?:hey\s+nova\b|nova\b|please\b|can\s+you\b|could\s+you\b|would\s+you\b|tell\s+me\b|i\s+want\s+to\b|help\s+me\b|just\b)\s*",
    re.IGNORECASE,
)

# Trailing politeness to strip
TRAILING_FILLERS_REGEX = re.compile(
    r"\s*(?:please|thanks|thank\s+you|for\s+me)\s*$",
    re.IGNORECASE,
)

# Negation patterns that must prevent action execution
NEGATION_REGEX = re.compile(
    r"\b(?:don'?t|do\s+not|never|stop\s+(?:asking\s+me\s+to|telling\s+me\s+to)|cancel)\b",
    re.IGNORECASE,
)

# Non-command colloquial idioms containing action keywords that must NOT trigger actions
NON_COMMAND_IDIOMS: list[str] = [
    "locked my keys",
    "lock ness",
    "padlock",
    "lock the front door",
    "volume of a sphere",
    "volume of a cylinder",
    "volume of sales",
    "play it by ear",
    "quit his job",
    "quit her job",
    "quit playing",
    "quit complaining",
    "close the window",
    "close the door",
    "pause and reflect",
    "pause and think",
    "pause for effect",
    "next level",
    "next year",
    "moot point",
    "mute point",
    "mute button is broken",
    "sleep is important",
    "sleep early",
    "sleep apnea",
    "sleepy hollow",
    "dream about",
    "turn up the heat",
    "turn down the heating",
    "time flies",
    "start from scratch",
    "stop making",
    "reset your mindset",
    "search your feelings",
    "nova scotia",
    "bossa nova",
    "supernova",
    "hey jeff",
    "hey nathan",
    "turn it upside down",
    "who is playing",
    "previous generations",
    "dark mode of",
]

# Non-command general questions (unless search requested)
GENERAL_QUESTION_PREFIXES = (
    "what is",
    "what's",
    "who is",
    "who was",
    "why is",
    "how tall",
    "how much does",
    "how are you",
    "what time",
    "where is",
    "hello there",
    "good morning",
    "good evening",
    "tell me a joke",
    "tell me about",
)


class Tier1IntentEngine(IntentEngineProtocol):
    """Offline, deterministic rule-based intent engine for NOVA."""

    def __init__(
        self,
        settings: NovaSettings | None = None,
        app_registry: AppRegistry | None = None,
    ) -> None:
        self.settings = settings or NovaSettings()
        aliases = self.settings.apps.aliases if hasattr(self.settings, "apps") else {}
        self.app_registry = app_registry or AppRegistry(
            registered_apps=DEFAULT_REGISTERED_APPS,
            aliases=aliases,
        )

    def resolve_intent(self, text: str) -> ActionRequest | None:
        """Parse natural language into a validated, allowlisted ActionRequest."""
        raw_text = text.strip()
        if not raw_text:
            return None

        # 1. Clean query of leading/trailing filler phrases
        clean = self._clean_query(raw_text)
        if not clean:
            return None

        # 2. Check for negation
        if NEGATION_REGEX.search(clean):
            logger.debug("Rejected query due to negation: '%s'", raw_text)
            return None

        # 3. Check for non-command idioms
        lower_clean = clean.lower()
        if any(idiom in lower_clean for idiom in NON_COMMAND_IDIOMS):
            logger.debug("Rejected non-command idiom: '%s'", raw_text)
            return None

        # 4. Check for general questions that shouldn't trigger actions
        if not lower_clean.startswith(("search", "google", "look up")) and any(
            lower_clean.startswith(prefix) for prefix in GENERAL_QUESTION_PREFIXES
        ):
            logger.debug("Rejected conversational question: '%s'", raw_text)
            return None

        # 5. Route to deterministic category matchers
        matchers = [
            self._match_web_search,
            self._match_web_open_url,
            self._match_volume_set,
            self._match_app_volume,
            self._match_volume_up_down,
            self._match_volume_mute,
            self._match_media_controls,
            self._match_system_power,
            self._match_dark_mode,
            self._match_stopwatch,
            self._match_timer,
            self._match_reminder,
            self._match_note,
            self._match_keyboard_type,
            self._match_keyboard_press,
            self._match_app_launch_or_close,
        ]

        for matcher in matchers:
            req = matcher(clean, raw_text)
            if req is not None:
                # Apply high-confidence threshold for destructive actions
                if req.is_destructive and req.confidence < 0.85:
                    logger.warning(
                        "Rejected destructive action '%s' with low confidence %.2f",
                        req.action_id,
                        req.confidence,
                    )
                    return None

                # Strict allowlist validation
                AllowlistValidator.validate(req)
                return req

        return None

    def resolve_compound(self, text: str) -> list[ActionRequest]:
        """Resolve a potentially compound voice command into atomic ActionRequests."""
        parts = split_compound_commands(text, self.resolve_intent)
        results: list[ActionRequest] = []
        for part in parts:
            req = self.resolve_intent(part)
            if req is not None:
                results.append(req)
        return results

    def _clean_query(self, text: str) -> str:
        """Strip wake words and polite padding."""
        s = text.strip()
        s = LEADING_FILLERS_REGEX.sub("", s)
        s = TRAILING_FILLERS_REGEX.sub("", s)
        return s.strip()

    # --- Matcher Implementations ---

    def _match_web_search(self, clean: str, raw: str) -> ActionRequest | None:
        """Match explicit web search commands."""
        m = re.match(r"^(?:search\s+for|google|search|look\s+up)\s+(.+)$", clean, re.IGNORECASE)
        if m:
            query = m.group(1).strip()
            # Do not match if query is empty or just "for"
            if query and query.lower() != "for":
                return ActionRequest(
                    action_id=ActionID.WEB_SEARCH.value,
                    parameters={"query": query},
                    confidence=0.95,
                    feedback_phrase=f"Searching the web for {query}.",
                    raw_query=raw,
                )
        return None

    def _match_web_open_url(self, clean: str, raw: str) -> ActionRequest | None:
        """Match direct website URL navigation."""
        m = re.match(
            r"^(?:open|go\s+to|visit)\s+(https?://\S+|[a-zA-Z0-9_\-]+\.(?:com|org|net|io|dev|edu|gov)(?:/\S*)?)$",
            clean,
            re.IGNORECASE,
        )
        if m:
            target = m.group(1).strip()
            url = target if target.startswith(("http://", "https://")) else f"https://{target}"
            return ActionRequest(
                action_id=ActionID.WEB_OPEN_URL.value,
                parameters={"url": url},
                confidence=0.95,
                feedback_phrase=f"Opening website {target}.",
                raw_query=raw,
            )
        return None

    def _match_app_volume(self, clean: str, raw: str) -> ActionRequest | None:
        """Match per-application volume controls."""
        # "set spotify volume to 40"
        m_set = re.match(
            r"^(?:set|change)\s+([a-zA-Z0-9_\-]+)\s+volume\s+(?:to\s+)?(.+)$",
            clean,
            re.IGNORECASE,
        )
        if m_set:
            app_raw = m_set.group(1).strip()
            if app_raw.lower() not in ("the", "master", "my", "system", "audio", "sound"):
                val = parse_number(m_set.group(2))
                if val is not None and 0 <= val <= 100:
                    return ActionRequest(
                        action_id=ActionID.VOLUME_APP_SET.value,
                        parameters={"app_name": app_raw, "percent": val, "direction": "set"},
                        confidence=0.95,
                        feedback_phrase=f"Setting {app_raw} volume to {val} percent.",
                        raw_query=raw,
                    )

        # "mute discord"
        m_mute = re.match(r"^mute\s+([a-zA-Z0-9_\-]+)$", clean, re.IGNORECASE)
        if m_mute:
            app_raw = m_mute.group(1).strip()
            # Verify app name is not a generic word like "sound", "audio", "mic"
            if app_raw not in (
                "sound",
                "audio",
                "speaker",
                "speakers",
                "mic",
                "microphone",
                "the",
                "system",
            ):
                return ActionRequest(
                    action_id=ActionID.VOLUME_APP_SET.value,
                    parameters={"app_name": app_raw, "direction": "mute"},
                    confidence=0.90,
                    feedback_phrase=f"Muting {app_raw}.",
                    raw_query=raw,
                )

        # "turn down chrome volume" / "turn up vlc volume"
        m_dir = re.match(
            r"^turn\s+(up|down)\s+([a-zA-Z0-9_\-]+)\s+volume$",
            clean,
            re.IGNORECASE,
        )
        if m_dir:
            direction = m_dir.group(1).lower()
            app_raw = m_dir.group(2).strip()
            if app_raw.lower() not in ("the", "master", "my", "system", "audio", "sound"):
                return ActionRequest(
                    action_id=ActionID.VOLUME_APP_SET.value,
                    parameters={"app_name": app_raw, "direction": direction},
                    confidence=0.90,
                    feedback_phrase=f"Turning {direction} {app_raw} volume.",
                    raw_query=raw,
                )

        return None

    def _match_volume_set(self, clean: str, raw: str) -> ActionRequest | None:
        """Match master volume set commands."""
        # "set volume to 50", "volume 70", "turn volume to seventy percent", "set the volume to sixty"
        m = re.match(
            r"^(?:(?:set|turn|change|adjust|make)\s+(?:the\s+|master\s+|system\s+)?(?:volume|sound|audio)\s+(?:to\s+)?|volume\s+)(.+)$",
            clean,
            re.IGNORECASE,
        )
        if m:
            num_str = m.group(1).strip()
            # If "up" or "down" was captured, pass to up/down matcher
            if num_str.lower() in ("up", "down"):
                return None
            val = parse_number(num_str)
            if val is not None and 0 <= val <= 100:
                return ActionRequest(
                    action_id=ActionID.VOLUME_SET.value,
                    parameters={"percent": val},
                    confidence=0.98,
                    feedback_phrase=f"Setting volume to {val} percent.",
                    raw_query=raw,
                )
        return None

    def _match_volume_up_down(self, clean: str, raw: str) -> ActionRequest | None:
        """Match relative volume increases and decreases."""
        lower = clean.lower()
        up_triggers = [
            "volume up",
            "turn volume up",
            "turn it up",
            "louder",
            "make it louder",
            "increase volume",
            "increase the volume",
            "raise volume",
            "raise the volume",
            "boost volume",
            "boost the volume",
            "a little louder",
        ]
        if any(lower == t or lower.startswith(t + " ") for t in up_triggers):
            return ActionRequest(
                action_id=ActionID.VOLUME_UP.value,
                confidence=0.95,
                feedback_phrase="Turning volume up.",
                raw_query=raw,
            )

        down_triggers = [
            "volume down",
            "turn volume down",
            "turn it down",
            "quieter",
            "make it quieter",
            "decrease volume",
            "decrease the volume",
            "lower volume",
            "lower the volume",
            "soften sound",
            "drop volume",
            "drop the volume",
        ]
        if any(lower == t or lower.startswith(t + " ") for t in down_triggers):
            return ActionRequest(
                action_id=ActionID.VOLUME_DOWN.value,
                confidence=0.95,
                feedback_phrase="Turning volume down.",
                raw_query=raw,
            )

        return None

    def _match_volume_mute(self, clean: str, raw: str) -> ActionRequest | None:
        """Match audio mute / unmute toggle."""
        lower = clean.lower()
        mute_triggers = [
            "mute",
            "unmute",
            "mute audio",
            "mute sound",
            "mute the sound",
            "toggle mute",
            "silence sound",
            "silence the speakers",
            "unmute sound",
        ]
        if lower in mute_triggers:
            return ActionRequest(
                action_id=ActionID.VOLUME_MUTE_TOGGLE.value,
                confidence=0.98,
                feedback_phrase="Toggled audio mute.",
                raw_query=raw,
            )
        return None

    def _match_media_controls(self, clean: str, raw: str) -> ActionRequest | None:
        """Match media play, pause, next, and previous."""
        lower = clean.lower()

        # Play / Pause
        play_pause_triggers = [
            "play",
            "pause",
            "resume",
            "pause music",
            "resume music",
            "play song",
            "toggle playback",
            "pause playback",
            "resume playback",
            "stop the music",
            "unpause",
            "unpause the music",
        ]
        if lower in play_pause_triggers or re.match(
            r"^(?:play|pause|resume|stop|unpause)\s+(?:the\s+)?(?:music|song|track|playback)$",
            lower,
        ):
            return ActionRequest(
                action_id=ActionID.MEDIA_PLAY_PAUSE.value,
                confidence=0.95,
                feedback_phrase="Toggled media playback.",
                raw_query=raw,
            )

        # Next
        next_triggers = [
            "next",
            "next track",
            "next song",
            "skip",
            "skip song",
            "skip track",
            "play next",
            "play next track",
        ]
        if lower in next_triggers:
            return ActionRequest(
                action_id=ActionID.MEDIA_NEXT.value,
                confidence=0.95,
                feedback_phrase="Playing next track.",
                raw_query=raw,
            )

        # Previous
        prev_triggers = [
            "previous",
            "previous track",
            "previous song",
            "go back a track",
            "last song",
            "replay previous track",
        ]
        if lower in prev_triggers:
            return ActionRequest(
                action_id=ActionID.MEDIA_PREVIOUS.value,
                confidence=0.95,
                feedback_phrase="Playing previous track.",
                raw_query=raw,
            )

        if lower.startswith("play ") and not any(idiom in lower for idiom in NON_COMMAND_IDIOMS):
            return ActionRequest(
                action_id=ActionID.MEDIA_PLAY_PAUSE.value,
                confidence=0.90,
                feedback_phrase="Playing media.",
                raw_query=raw,
            )

        return None

    def _match_system_power(self, clean: str, raw: str) -> ActionRequest | None:
        """Match workstation lock and sleep (destructive actions)."""
        lower = clean.lower()

        lock_triggers = [
            "lock",
            "lock pc",
            "lock computer",
            "lock screen",
            "lock workstation",
            "lock the desktop",
            "lock the computer",
        ]
        if lower in lock_triggers:
            return ActionRequest(
                action_id=ActionID.SYSTEM_LOCK.value,
                confidence=0.95,
                is_destructive=True,
                feedback_phrase="Locking workstation.",
                raw_query=raw,
            )

        sleep_triggers = [
            "sleep",
            "suspend",
            "put pc to sleep",
            "put computer to sleep",
            "standby mode",
            "suspend the system",
        ]
        if lower in sleep_triggers:
            return ActionRequest(
                action_id=ActionID.SYSTEM_SLEEP.value,
                confidence=0.95,
                is_destructive=True,
                feedback_phrase="Suspending system.",
                raw_query=raw,
            )

        return None

    def _match_dark_mode(self, clean: str, raw: str) -> ActionRequest | None:
        """Match system appearance theme toggles."""
        lower = clean.lower()
        theme_triggers = [
            "dark mode",
            "toggle dark mode",
            "switch to dark mode",
            "light mode",
            "toggle light mode",
            "switch theme",
            "toggle dark theme",
        ]
        if lower in theme_triggers:
            return ActionRequest(
                action_id=ActionID.DARK_MODE_TOGGLE.value,
                confidence=0.95,
                feedback_phrase="Toggled system appearance theme.",
                raw_query=raw,
            )
        return None

    def _match_stopwatch(self, clean: str, raw: str) -> ActionRequest | None:
        """Match stopwatch commands."""
        lower = clean.lower()
        if lower in ("start stopwatch", "begin stopwatch"):
            return ActionRequest(
                action_id=ActionID.STOPWATCH_START.value,
                confidence=0.95,
                feedback_phrase="Started stopwatch.",
                raw_query=raw,
            )
        if lower in ("stop stopwatch", "pause stopwatch"):
            return ActionRequest(
                action_id=ActionID.STOPWATCH_STOP.value,
                confidence=0.95,
                feedback_phrase="Stopped stopwatch.",
                raw_query=raw,
            )
        if lower in ("reset stopwatch", "clear stopwatch"):
            return ActionRequest(
                action_id=ActionID.STOPWATCH_RESET.value,
                confidence=0.95,
                feedback_phrase="Reset stopwatch.",
                raw_query=raw,
            )
        if lower in ("stopwatch status", "how much time on stopwatch"):
            return ActionRequest(
                action_id=ActionID.STOPWATCH_STATUS.value,
                confidence=0.95,
                feedback_phrase="Checking stopwatch status.",
                raw_query=raw,
            )
        return None

    def _match_timer(self, clean: str, raw: str) -> ActionRequest | None:
        """Match timer setup commands."""
        m = re.match(
            r"^(?:set\s+a\s+timer\s+for|set\s+timer\s+for|timer)\s+(.+)$",
            clean,
            re.IGNORECASE,
        )
        if m:
            dur_str = m.group(1).strip()
            duration = parse_duration(dur_str)
            if duration is not None and duration > 0:
                return ActionRequest(
                    action_id=ActionID.TIMER_SET.value,
                    parameters={"duration_seconds": duration},
                    confidence=0.95,
                    feedback_phrase=f"Setting a timer for {dur_str}.",
                    raw_query=raw,
                )
        return None

    def _match_reminder(self, clean: str, raw: str) -> ActionRequest | None:
        """Match reminder scheduling commands."""
        m = re.match(
            r"^(?:remind\s+me\s+to|set\s+a\s+reminder\s+to|create\s+a\s+reminder\s+to|set\s+reminder\s+to)\s+(.+)$",
            clean,
            re.IGNORECASE,
        )
        if m:
            rest = m.group(1).strip()
            # Check for " in <duration>"
            time_split = re.split(r"\s+in\s+", rest, flags=re.IGNORECASE)
            if len(time_split) > 1:
                reminder_text = time_split[0].strip()
                dur_str = time_split[1].strip()
                dur_sec = parse_duration(dur_str)
                params: dict[str, Any] = {"text": reminder_text}
                if dur_sec:
                    params["seconds"] = dur_sec
                return ActionRequest(
                    action_id=ActionID.REMINDER_SET.value,
                    parameters=params,
                    confidence=0.90,
                    feedback_phrase=f"Reminder set for {reminder_text}.",
                    raw_query=raw,
                )
            else:
                return ActionRequest(
                    action_id=ActionID.REMINDER_SET.value,
                    parameters={"text": rest},
                    confidence=0.85,
                    feedback_phrase=f"Reminder set for {rest}.",
                    raw_query=raw,
                )
        return None

    def _match_note(self, clean: str, raw: str) -> ActionRequest | None:
        """Match note append commands."""
        m = re.match(
            r"^(?:take\s+a\s+note|note\s+that|write\s+this\s+down|add\s+a\s+note|add\s+note)\s+(.+)$",
            clean,
            re.IGNORECASE,
        )
        if m:
            note_text = m.group(1).strip()
            if note_text:
                return ActionRequest(
                    action_id=ActionID.NOTE_APPEND.value,
                    parameters={"text": note_text},
                    confidence=0.95,
                    feedback_phrase="Saved your note.",
                    raw_query=raw,
                )
        return None

    def _match_keyboard_type(self, clean: str, raw: str) -> ActionRequest | None:
        """Match keyboard typing commands (e.g. 'type hello world', 'write hello')."""
        m = re.match(
            r"^(?:type|write|type\s+in|type\s+out)\s+(.+)$",
            clean,
            re.IGNORECASE,
        )
        if m:
            text_to_type = m.group(1).strip()
            # If text_to_type is enclosed in quotes, strip them
            if (text_to_type.startswith('"') and text_to_type.endswith('"')) or (
                text_to_type.startswith("'") and text_to_type.endswith("'")
            ):
                text_to_type = text_to_type[1:-1].strip()
            if text_to_type:
                return ActionRequest(
                    action_id=ActionID.KEYBOARD_TYPE.value,
                    parameters={"text": text_to_type},
                    confidence=0.95,
                    feedback_phrase="Typing text.",
                    raw_query=raw,
                )
        return None

    def _match_keyboard_press(self, clean: str, raw: str) -> ActionRequest | None:
        """Match keyboard key press commands (e.g. 'press enter', 'hit enter', 'press the tab key')."""
        m = re.match(
            r"^(?:press|hit|tap)(?:\s+the)?\s+([a-zA-Z0-9_\-]+)(?:\s+key)?$",
            clean,
            re.IGNORECASE,
        )
        if m:
            key_name = m.group(1).lower().strip()
            if key_name in ALLOWED_KEYBOARD_KEYS:
                return ActionRequest(
                    action_id=ActionID.KEYBOARD_PRESS.value,
                    parameters={"key": key_name},
                    confidence=0.95,
                    feedback_phrase=f"Pressing {key_name}.",
                    raw_query=raw,
                )
        return None

    def _match_app_launch_or_close(self, clean: str, raw: str) -> ActionRequest | None:
        """Match application launch and close using registry and RapidFuzz."""
        # Launch: open / launch / start
        m_open = re.match(r"^(?:open|launch|start)\s+([a-zA-Z0-9_\-\.\s]+)$", clean, re.IGNORECASE)
        if m_open:
            app_query = m_open.group(1).strip()
            res = self.app_registry.match_app(app_query)
            if res.status == "exact" and res.matched_name:
                return ActionRequest(
                    action_id=ActionID.APP_LAUNCH.value,
                    parameters={"app_name": res.matched_name},
                    confidence=res.confidence,
                    feedback_phrase=f"Opening {res.matched_name}.",
                    raw_query=raw,
                )
            elif res.status == "ambiguous":
                logger.info(
                    "App query '%s' was ambiguous between candidates: %s",
                    app_query,
                    res.candidates,
                )
                return None

        # Close: close / quit / terminate / exit
        m_close = re.match(
            r"^(?:close|quit|terminate|exit)\s+([a-zA-Z0-9_\-\.\s]+)$", clean, re.IGNORECASE
        )
        if m_close:
            app_query = m_close.group(1).strip()
            res = self.app_registry.match_app(app_query)
            if res.status == "exact" and res.matched_name:
                return ActionRequest(
                    action_id=ActionID.APP_CLOSE.value,
                    parameters={"app_name": res.matched_name},
                    confidence=res.confidence,
                    is_destructive=True,
                    feedback_phrase=f"Closing {res.matched_name}.",
                    raw_query=raw,
                )

        return None
