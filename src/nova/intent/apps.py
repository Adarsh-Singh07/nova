"""Registry-based application matching with RapidFuzz and ambiguity margins.

Enforces Rule R5: Applications resolve strictly to registered/allowlisted applications.
Includes a minimum match score (75) and an ambiguity margin (10 points) to prompt
for clarification when two candidates score closely.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import rapidfuzz.fuzz
import rapidfuzz.process


@dataclass(frozen=True)
class AppMatchResult:
    """Outcome of resolving a spoken query to an application."""

    status: str  # "exact", "ambiguous", "none"
    matched_name: str | None = None
    confidence: float = 0.0
    candidates: list[tuple[str, float]] = field(default_factory=list)


# Standard default registered desktop applications
DEFAULT_REGISTERED_APPS: list[str] = [
    "Visual Studio Code",
    "Google Chrome",
    "Windows Terminal",
    "Command Prompt",
    "Calculator",
    "Spotify",
    "Slack",
    "Notepad",
    "File Explorer",
    "Mozilla Firefox",
    "VLC Media Player",
    "Discord",
    "Notes and Reminders",
]


class AppRegistry:
    """Manages registered applications, aliases, and fuzzy matching."""

    def __init__(
        self,
        registered_apps: list[str] | None = None,
        aliases: dict[str, str] | None = None,
        min_score: float = 75.0,
        ambiguity_margin: float = 10.0,
    ) -> None:
        self.registered_apps = list(registered_apps or DEFAULT_REGISTERED_APPS)
        self.aliases = dict(aliases or {})
        self.min_score = min_score
        self.ambiguity_margin = ambiguity_margin

    def register_app(self, app_name: str) -> None:
        """Register an application name."""
        if app_name not in self.registered_apps:
            self.registered_apps.append(app_name)

    def set_alias(self, alias: str, target_name: str) -> None:
        """Add or update an alias mapping."""
        self.aliases[alias.lower().strip()] = target_name

    def match_app(self, query: str) -> AppMatchResult:
        """Resolve a spoken app query to an allowlisted application.

        Resolution order:
        1. Exact alias match (e.g. "code" -> "Visual Studio Code").
        2. Exact case-insensitive registry match.
        3. Fuzzy token_sort_ratio matching across registry and aliases.
        """
        clean_query = query.lower().strip()
        if not clean_query:
            return AppMatchResult(status="none")

        # 1. Direct alias match
        if clean_query in self.aliases:
            target = self.aliases[clean_query]
            return AppMatchResult(
                status="exact",
                matched_name=target,
                confidence=1.0,
                candidates=[(target, 100.0)],
            )

        # 2. Direct match with registered app
        for app in self.registered_apps:
            if clean_query == app.lower():
                return AppMatchResult(
                    status="exact",
                    matched_name=app,
                    confidence=1.0,
                    candidates=[(app, 100.0)],
                )

        # 3. RapidFuzz matching across registry and aliases
        # Build candidate pool mapping display name -> canonical registered name
        candidate_pool: dict[str, str] = {}
        for app in self.registered_apps:
            candidate_pool[app] = app
        for alias, target in self.aliases.items():
            candidate_pool[alias] = target

        choices = list(candidate_pool.keys())
        results = rapidfuzz.process.extract(
            clean_query,
            choices,
            scorer=rapidfuzz.fuzz.token_sort_ratio,
            processor=lambda s: s.lower(),
            limit=5,
        )

        if not results:
            return AppMatchResult(status="none")

        # Filter by minimum score
        valid_results = [r for r in results if r[1] >= self.min_score]
        if not valid_results:
            return AppMatchResult(status="none")

        top_match_str, top_score, _ = valid_results[0]
        top_app = candidate_pool[top_match_str]

        # Check for ambiguity margin with runner-up
        if len(valid_results) > 1:
            runner_up_str, runner_up_score, _ = valid_results[1]
            runner_up_app = candidate_pool[runner_up_str]

            # If both point to different applications and score is within margin
            if runner_up_app != top_app and (top_score - runner_up_score) < self.ambiguity_margin:
                return AppMatchResult(
                    status="ambiguous",
                    matched_name=None,
                    confidence=top_score / 100.0,
                    candidates=[(top_app, top_score), (runner_up_app, runner_up_score)],
                )

        return AppMatchResult(
            status="exact",
            matched_name=top_app,
            confidence=top_score / 100.0,
            candidates=[(top_app, top_score)],
        )
