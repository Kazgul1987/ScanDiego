from __future__ import annotations
import difflib, re, unicodedata
from dataclasses import dataclass
from app.models.metadata import ExternalGame


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


@dataclass(slots=True)
class ScoredMatch:
    game: ExternalGame
    score: float
    platform_match: bool


class GameMatchingService:
    def __init__(self, automatic_threshold=90.0, ambiguous_threshold=75.0):
        self.automatic_threshold, self.ambiguous_threshold = automatic_threshold, ambiguous_threshold

    def score(self, title: str, platform: str, candidate: ExternalGame, release_year: int | None = None) -> ScoredMatch:
        title_score = difflib.SequenceMatcher(None, normalize(title), normalize(candidate.title)).ratio() * 75
        local_platform, remote_platform = normalize(platform), normalize(candidate.platform)
        aliases = {"ps2": "playstation 2", "ps3": "playstation 3", "ps4": "playstation 4", "ps5": "playstation 5", "switch": "nintendo switch"}
        local_platform, remote_platform = aliases.get(local_platform, local_platform), aliases.get(remote_platform, remote_platform)
        platform_match = bool(local_platform and remote_platform and local_platform == remote_platform)
        # A known conflict is a hard cap, so title identity can never auto-match it.
        if local_platform != "unknown" and remote_platform and not platform_match:
            return ScoredMatch(candidate, min(55.0, title_score), False)
        result = title_score + (25 if platform_match else 5)
        if release_year and candidate.release_year: result += 5 if release_year == candidate.release_year else -min(15, abs(release_year-candidate.release_year)*3)
        return ScoredMatch(candidate, round(max(0, min(100, result)), 2), platform_match)

    def rank(self, title: str, platform: str, candidates: list[ExternalGame], release_year=None) -> list[ScoredMatch]:
        return sorted((self.score(title, platform, x, release_year) for x in candidates), key=lambda x: x.score, reverse=True)

    def classify(self, ranked: list[ScoredMatch]) -> str:
        if not ranked or ranked[0].score < self.ambiguous_threshold: return "failed"
        if ranked[0].score < self.automatic_threshold: return "ambiguous"
        if len(ranked) > 1 and ranked[1].score >= self.ambiguous_threshold and ranked[0].score-ranked[1].score < 5: return "ambiguous"
        return "matched"
