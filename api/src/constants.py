"""Application constants and enums - source of truth for validation."""
from enum import Enum


class ObservationStatus(str, Enum):
    """Observation extraction status."""
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    LOW_CONFIDENCE = "low_confidence"
    UNMATCHED = "unmatched"
    OCCLUDED = "occluded"
    UNREADABLE = "unreadable"


class ShelfPosition(str, Enum):
    """Shelf position classification."""
    TOP = "top"
    EYE_LEVEL = "eye_level"
    REACH = "reach"
    STOOP = "stoop"
    BOTTOM = "bottom"
    ENDCAP = "endcap"
    COOLER_DOOR = "cooler_door"
    UNKNOWN = "unknown"


class Legibility(str, Enum):
    """Image legibility for observation."""
    FULLY_READABLE = "fully_readable"
    PARTIAL = "partial"
    UNREADABLE = "unreadable"


class ObjectType(str, Enum):
    """Detected object type."""
    BOTTLE = "bottle"
    CAN = "can"
    PLASTIC_BOTTLE = "plastic_bottle"
    GLASS_BOTTLE = "glass_bottle"
    BOX = "box"
    OTHER = "other"


class AuditStatus(str, Enum):
    """Audit overall status."""
    PROCESSING = "processing"
    FINAL = "final"
    RETAKE_REQUIRED = "retake_required"
    GUARDRAIL_REJECTED = "guardrail_rejected"


class MatchMethod(str, Enum):
    """SKU matching method."""
    EXACT = "exact"
    FUZZY = "fuzzy"
    EMBEDDING = "embedding"
    UNRESOLVED = "unresolved"


# Allowed values for database validation
VALID_STATUSES = [e.value for e in ObservationStatus]
VALID_POSITIONS = [e.value for e in ShelfPosition]
VALID_LEGIBILITIES = [e.value for e in Legibility]
VALID_OBJECT_TYPES = [e.value for e in ObjectType]
