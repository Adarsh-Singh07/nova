"""Comprehensive test suite for NOVA Tier 1 Intent Engine (Phase 3).

Evaluates:
- Number and duration parsers.
- AppRegistry fuzzy matching and ambiguity margin.
- Safe compound splitting (two-half validation).
- Destructive intent high-confidence gating and R5.5 confirmation flow.
- Full frozen held-out test suite (200+ samples) with confusion matrix,
  per-intent precision/recall, and false-action rate on non-commands.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nova.core.actions import ActionID
from nova.core.fakes import FakePlatformAdapter, FakeTTSEngine
from nova.core.interfaces import ActionRequest, ConfirmationHandlerProtocol
from nova.core.pipeline import NovaPipeline
from nova.core.settings import NovaSettings
from nova.intent.apps import AppRegistry
from nova.intent.compound import split_compound_commands
from nova.intent.numbers import parse_duration, parse_number
from nova.intent.tier1 import Tier1IntentEngine

HELDOUT_PATH = Path(__file__).parent / "data" / "intent_heldout_set.json"
DEV_PATH = Path(__file__).parent / "data" / "intent_dev_set.json"


# ---------------------------------------------------------------------------
# 1. Number and Duration Parsing Tests
# ---------------------------------------------------------------------------
def test_parse_number_digits() -> None:
    assert parse_number("50") == 50
    assert parse_number("0") == 0
    assert parse_number("100") == 100
    assert parse_number("75%") == 75
    assert parse_number("80 percent") == 80


def test_parse_number_words() -> None:
    assert parse_number("twenty five") == 25
    assert parse_number("seventy") == 70
    assert parse_number("one hundred") == 100
    assert parse_number("forty five percent") == 45
    assert parse_number("zero") == 0
    assert parse_number("twelve") == 12
    assert parse_number("ninety nine") == 99
    assert parse_number("not a number") is None


def test_parse_duration() -> None:
    assert parse_duration("half an hour") == 1800.0
    assert parse_duration("an hour") == 3600.0
    assert parse_duration("one hour") == 3600.0
    assert parse_duration("two and a half minutes") == 150.0
    assert parse_duration("10 minutes") == 600.0
    assert parse_duration("twenty five minutes") == 1500.0
    assert parse_duration("30 seconds") == 30.0
    assert parse_duration("forty five seconds") == 45.0
    assert parse_duration("5 minutes and 30 seconds") == 330.0
    assert parse_duration("two hours and 15 minutes") == 8100.0


# ---------------------------------------------------------------------------
# 2. AppRegistry and RapidFuzz Matching Tests
# ---------------------------------------------------------------------------
def test_app_registry_exact_alias() -> None:
    reg = AppRegistry(
        registered_apps=["Visual Studio Code", "Google Chrome"],
        aliases={"code": "Visual Studio Code", "browser": "Google Chrome"},
    )
    res = reg.match_app("code")
    assert res.status == "exact"
    assert res.matched_name == "Visual Studio Code"
    assert res.confidence == 1.0


def test_app_registry_fuzzy_typo() -> None:
    reg = AppRegistry(
        registered_apps=["Calculator", "Spotify"],
        aliases={"calc": "Calculator"},
    )
    # Typo: "calclator"
    res = reg.match_app("calclator")
    assert res.status == "exact"
    assert res.matched_name == "Calculator"
    assert res.confidence >= 0.75

    # Typo: "spottify"
    res_spot = reg.match_app("spottify")
    assert res_spot.status == "exact"
    assert res_spot.matched_name == "Spotify"


def test_app_registry_ambiguity_margin() -> None:
    # Two candidates with very close names
    reg = AppRegistry(
        registered_apps=["Google Chrome", "Google Chromium"],
        min_score=75.0,
        ambiguity_margin=15.0,
    )
    res = reg.match_app("google chrom")
    # Both score high and close together -> must flag ambiguous rather than guessing
    assert res.status == "ambiguous"
    assert res.matched_name is None
    assert len(res.candidates) >= 2


def test_app_registry_unknown_returns_none() -> None:
    reg = AppRegistry(registered_apps=["Calculator", "Spotify"])
    res = reg.match_app("quantum computer simulator 9000")
    assert res.status == "none"
    assert res.matched_name is None


# ---------------------------------------------------------------------------
# 3. Compound Command Splitting Invariant Tests
# ---------------------------------------------------------------------------
def test_compound_split_valid_pairs() -> None:
    engine = Tier1IntentEngine()
    parts = split_compound_commands("pause the music and open slack", engine.resolve_intent)
    assert parts == ["pause the music", "open slack"]

    parts_then = split_compound_commands(
        "turn volume up then lock workstation", engine.resolve_intent
    )
    assert parts_then == ["turn volume up", "lock workstation"]


def test_compound_non_split_invariants() -> None:
    engine = Tier1IntentEngine()

    # "search salt and pepper" -> right side "pepper" is NOT a command -> DO NOT SPLIT
    parts1 = split_compound_commands("search salt and pepper", engine.resolve_intent)
    assert parts1 == ["search salt and pepper"]

    # "play rock and roll" -> right side "roll" is NOT a command -> DO NOT SPLIT
    parts2 = split_compound_commands("play rock and roll", engine.resolve_intent)
    assert parts2 == ["play rock and roll"]

    # "open notes and reminders" -> right side "reminders" is NOT a command -> DO NOT SPLIT
    parts3 = split_compound_commands("open notes and reminders", engine.resolve_intent)
    assert parts3 == ["open notes and reminders"]


# ---------------------------------------------------------------------------
# 4. Destructive Intent Confidence & R5.5 Confirmation Flow Tests
# ---------------------------------------------------------------------------
class MockConfirmationHandler(ConfirmationHandlerProtocol):
    def __init__(self, approve: bool) -> None:
        self.approve = approve
        self.call_count = 0
        self.last_action: ActionRequest | None = None

    def request_confirmation(self, action: ActionRequest) -> bool:
        self.call_count += 1
        self.last_action = action
        return self.approve


def test_destructive_confirmation_approved() -> None:
    engine = Tier1IntentEngine()
    platform = FakePlatformAdapter()
    tts = FakeTTSEngine()
    settings = NovaSettings()
    settings.security.fast_mode = False

    confirm_handler = MockConfirmationHandler(approve=True)
    pipeline = NovaPipeline(
        settings=settings,
        intent_engine=engine,
        platform_adapter=platform,
        tts_engine=tts,
        confirmation_handler=confirm_handler,
    )

    result = pipeline.process_text("lock workstation")
    assert confirm_handler.call_count == 1
    assert result.success is True
    assert result.action_request is not None
    assert result.spoken_feedback == "Workstation locked"


def test_destructive_confirmation_rejected() -> None:
    engine = Tier1IntentEngine()
    platform = FakePlatformAdapter()
    tts = FakeTTSEngine()
    settings = NovaSettings()
    settings.security.fast_mode = False

    confirm_handler = MockConfirmationHandler(approve=False)
    pipeline = NovaPipeline(
        settings=settings,
        intent_engine=engine,
        platform_adapter=platform,
        tts_engine=tts,
        confirmation_handler=confirm_handler,
    )

    result = pipeline.process_text("lock workstation")
    assert confirm_handler.call_count == 1
    assert result.success is False
    assert result.error == "Action cancelled by user"
    assert result.spoken_feedback == "Action cancelled."


def test_destructive_fast_mode_bypasses_confirmation() -> None:
    engine = Tier1IntentEngine()
    platform = FakePlatformAdapter()
    tts = FakeTTSEngine()
    settings = NovaSettings()
    settings.security.fast_mode = True  # Fast mode enabled

    confirm_handler = MockConfirmationHandler(approve=False)
    pipeline = NovaPipeline(
        settings=settings,
        intent_engine=engine,
        platform_adapter=platform,
        tts_engine=tts,
        confirmation_handler=confirm_handler,
    )

    result = pipeline.process_text("lock workstation")
    assert confirm_handler.call_count == 0  # Bypassed
    assert result.success is True


# ---------------------------------------------------------------------------
# 5. Full Frozen Held-Out Test Suite & Metrics Evaluation
# ---------------------------------------------------------------------------
def test_heldout_dataset_evaluation() -> None:
    """Run evaluation over the frozen 200+ held-out test set.

    Computes:
    - Per-intent Precision & Recall
    - False-Action Rate on Non-Commands (Headline Metric)
    - Overall Accuracy (target > 98%)
    """
    assert HELDOUT_PATH.exists(), f"Held-out dataset missing at {HELDOUT_PATH}"

    with open(HELDOUT_PATH, encoding="utf-8") as f:
        samples: list[dict[str, Any]] = json.load(f)

    engine = Tier1IntentEngine()

    total_samples = len(samples)
    correct_count = 0

    # Metrics accumulators
    intent_classes = {
        ActionID.VOLUME_SET.value,
        ActionID.VOLUME_UP.value,
        ActionID.VOLUME_DOWN.value,
        ActionID.VOLUME_MUTE_TOGGLE.value,
        ActionID.VOLUME_APP_SET.value,
        ActionID.MEDIA_PLAY_PAUSE.value,
        ActionID.MEDIA_NEXT.value,
        ActionID.MEDIA_PREVIOUS.value,
        ActionID.SYSTEM_LOCK.value,
        ActionID.SYSTEM_SLEEP.value,
        ActionID.APP_LAUNCH.value,
        ActionID.APP_CLOSE.value,
        ActionID.DARK_MODE_TOGGLE.value,
        ActionID.TIMER_SET.value,
        ActionID.STOPWATCH_START.value,
        ActionID.STOPWATCH_STOP.value,
        ActionID.STOPWATCH_RESET.value,
        ActionID.STOPWATCH_STATUS.value,
        ActionID.REMINDER_SET.value,
        ActionID.NOTE_APPEND.value,
        ActionID.WEB_SEARCH.value,
        ActionID.WEB_OPEN_URL.value,
        "compound",
    }

    tp: dict[str, int] = dict.fromkeys(intent_classes, 0)
    fp: dict[str, int] = dict.fromkeys(intent_classes, 0)
    fn: dict[str, int] = dict.fromkeys(intent_classes, 0)

    total_negatives = 0
    false_actions_on_negatives = 0

    failures: list[dict[str, Any]] = []

    for item in samples:
        query = item["query"]
        expected_intent = item["expected_intent"]

        # Check if query is compound
        if expected_intent == "compound":
            compound_reqs = engine.resolve_compound(query)
            if len(compound_reqs) > 1:
                predicted_intent: str | None = "compound"
            elif compound_reqs:
                predicted_intent = compound_reqs[0].action_id
            else:
                predicted_intent = None
        else:
            req = engine.resolve_intent(query)
            predicted_intent = req.action_id if req is not None else None

        # Non-command evaluation
        if expected_intent is None:
            total_negatives += 1
            if predicted_intent is not None:
                false_actions_on_negatives += 1
                failures.append(
                    {
                        "query": query,
                        "expected": None,
                        "predicted": predicted_intent,
                        "type": "False Positive Non-Command",
                    }
                )
        else:
            if predicted_intent == expected_intent:
                correct_count += 1
                tp[expected_intent] += 1
            else:
                fn[expected_intent] += 1
                if predicted_intent is not None:
                    fp[predicted_intent] += 1
                failures.append(
                    {
                        "query": query,
                        "expected": expected_intent,
                        "predicted": predicted_intent,
                        "type": "Classification Mismatch",
                    }
                )

        # Negatives are also counted in overall accuracy if predicted is None
        if expected_intent is None and predicted_intent is None:
            correct_count += 1

    accuracy = (correct_count / total_samples) * 100.0
    false_action_rate = (
        (false_actions_on_negatives / total_negatives) * 100.0 if total_negatives > 0 else 0.0
    )

    # Print summary report
    print("\n" + "=" * 70)
    print("NOVA TIER 1 INTENT ENGINE — HELD-OUT TEST EVALUATION REPORT")
    print("=" * 70)
    print(f"Total Samples Evaluated:      {total_samples}")
    print(f"Total Correct:                {correct_count} / {total_samples}")
    print(f"Overall Accuracy:             {accuracy:.2f}% (Target: > 98.00%)")
    print(f"Total Non-Command Negatives:  {total_negatives}")
    print(f"False Actions on Negatives:   {false_actions_on_negatives}")
    print(f"HEADLINE METRIC (False Action Rate): {false_action_rate:.2f}% (Target: 0.00%)")
    print("-" * 70)
    print(f"{'Intent':<30} {'Precision':<12} {'Recall':<12} {'F1':<12}")
    print("-" * 70)

    for intent in sorted(intent_classes):
        p = tp[intent] / (tp[intent] + fp[intent]) if (tp[intent] + fp[intent]) > 0 else 1.0
        r = tp[intent] / (tp[intent] + fn[intent]) if (tp[intent] + fn[intent]) > 0 else 1.0
        f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
        if tp[intent] > 0 or fn[intent] > 0:
            print(f"{intent:<30} {p:<12.2f} {r:<12.2f} {f1:<12.2f}")

    print("=" * 70)

    if failures:
        print("\nFailures:")
        for fail in failures:
            print(
                f"  - [{fail['type']}] '{fail['query']}' -> Expected: {fail['expected']}, Got: {fail['predicted']}"
            )

    # Gating assertions
    assert false_action_rate == 0.0, (
        f"False action rate must be 0.00%, got {false_action_rate:.2f}%"
    )
    assert accuracy >= 98.0, f"Overall accuracy must be >= 98.00%, got {accuracy:.2f}%"


def test_dev_dataset_evaluation() -> None:
    """Run evaluation over the dev test set (108 samples)."""
    assert DEV_PATH.exists(), f"Dev dataset missing at {DEV_PATH}"

    with open(DEV_PATH, encoding="utf-8") as f:
        samples: list[dict[str, Any]] = json.load(f)

    engine = Tier1IntentEngine()

    total_samples = len(samples)
    correct_count = 0
    total_negatives = 0
    false_actions_on_negatives = 0

    for item in samples:
        query = item["query"]
        expected_intent = item["expected_intent"]

        if expected_intent == "compound":
            compound_reqs = engine.resolve_compound(query)
            predicted_intent: str | None = (
                "compound"
                if len(compound_reqs) > 1
                else (compound_reqs[0].action_id if compound_reqs else None)
            )
        else:
            req = engine.resolve_intent(query)
            predicted_intent = req.action_id if req is not None else None

        if expected_intent is None:
            total_negatives += 1
            if predicted_intent is not None:
                false_actions_on_negatives += 1
            else:
                correct_count += 1
        else:
            if predicted_intent == expected_intent:
                correct_count += 1

    accuracy = (correct_count / total_samples) * 100.0
    false_action_rate = (
        (false_actions_on_negatives / total_negatives) * 100.0 if total_negatives > 0 else 0.0
    )

    assert false_action_rate == 0.0, (
        f"Dev false action rate must be 0.00%, got {false_action_rate:.2f}%"
    )
    assert accuracy >= 98.0, f"Dev accuracy must be >= 98.00%, got {accuracy:.2f}%"
