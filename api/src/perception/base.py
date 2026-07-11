from dataclasses import dataclass, field, asdict
from typing import Literal

Verdict = Literal["pass", "warn", "reject"]


@dataclass
class QualityResult:
    overall_score: float
    blur_score: float
    exposure_score: float
    resolution_ok: bool
    aspect_ratio_ok: bool
    verdict: Verdict
    issues: list[str] = field(default_factory=list)
    retake_reason: str | None = None
    content_hash: str | None = None
    width: int = 0
    height: int = 0

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class GuardrailResult:
    verdict: Verdict  # pass, warn, reject
    category: str  # alcohol_type, non_alcohol, poor_quality, etc.
    confidence: float  # 0-1 score from CLIP/YOLO
    top_matches: list[tuple[str, float]]
    routing: Literal["shelf_extraction", "store_entry", "rejected"]
    reason: str | None = None

    # Grounded reasoning - why was this verdict made?
    rejection_reason: str | None = None  # e.g., "non_alcohol_detected (water_bottle, conf=0.92)"
    alcohol_type: str | None = None  # e.g., "beer", "wine", "spirits"
    alcohol_confidence: float | None = None  # confidence in alcohol type
    shelf_type: str | None = None  # e.g., "gondola", "cooler", "endcap"
    shelf_confidence: float | None = None

    def to_json(self) -> dict:
        return {
            "verdict": self.verdict,
            "category": self.category,
            "confidence": self.confidence,
            "top_matches": self.top_matches,
            "routing": self.routing,
            "reason": self.reason,
            "rejection_reason": self.rejection_reason,
            "alcohol_type": self.alcohol_type,
            "alcohol_confidence": self.alcohol_confidence,
            "shelf_type": self.shelf_type,
            "shelf_confidence": self.shelf_confidence,
        }
