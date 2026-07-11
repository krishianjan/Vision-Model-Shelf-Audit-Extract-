import hashlib
import os
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps

from src.perception.base import QualityResult

BLUR_THRESHOLD = float(os.getenv("QUALITY_LAPLACIAN_THRESHOLD", "80"))
EXPOSURE_MIN = float(os.getenv("QUALITY_EXPOSURE_MIN", "40"))
EXPOSURE_MAX = float(os.getenv("QUALITY_EXPOSURE_MAX", "240"))
MIN_LONGEST_EDGE = 640
IDEAL_MEAN = 130
CLAHE_TRIGGER_MEAN = 55


def _decode(image_bytes: bytes) -> tuple[np.ndarray, np.ndarray, int, int]:
    pil = Image.open(BytesIO(image_bytes))
    pil = ImageOps.exif_transpose(pil).convert("RGB")
    rgb = np.array(pil)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    return bgr, gray, int(w), int(h)


def _blur_score(gray: np.ndarray) -> tuple[float, float]:
    var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    normalized = float(min(1.0, var / (BLUR_THRESHOLD * 3)))
    return var, normalized


def _exposure_score(gray: np.ndarray) -> tuple[float, float]:
    mean = float(np.mean(gray))
    distance = abs(mean - IDEAL_MEAN) / IDEAL_MEAN
    normalized = float(max(0.0, 1.0 - distance))
    return mean, normalized
    return mean, normalized


def _apply_clahe(bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_eq = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l_eq, a, b)), cv2.COLOR_LAB2BGR)


def check_quality(image_bytes: bytes) -> tuple[QualityResult, bytes]:
    """
    Returns (result, possibly-rescued image bytes).
    If CLAHE rescue was applied, returned bytes reflect the rescued image.
    """
    bgr, gray, w, h = _decode(image_bytes)
    content_hash = hashlib.sha256(image_bytes).hexdigest()

    blur_var, blur_norm = _blur_score(gray)
    mean, exposure_norm = _exposure_score(gray)

    issues: list[str] = []
    verdict = "pass"
    retake_reason: str | None = None
    processed_bytes = image_bytes

    resolution_ok = max(w, h) >= MIN_LONGEST_EDGE
    if not resolution_ok:
        issues.append(f"resolution_too_low ({w}x{h}, need longest edge >={MIN_LONGEST_EDGE})")

    aspect = w / h if h else 0
    aspect_ratio_ok = 0.33 <= aspect <= 3.0
    if not aspect_ratio_ok:
        issues.append(f"aspect_ratio_extreme ({aspect:.2f})")

    # Blur evaluation — only reject extreme motion blur
    # Bare-minimum threshold: if Laplacian var < 50, image is too blurry to read ANY text
    if blur_var < 50:
        issues.append(f"severe_blur (laplacian_var={blur_var:.1f})")
        verdict = "reject"
        retake_reason = "Image is too blurry. Hold the phone steady and retake."
    elif blur_var < BLUR_THRESHOLD:
        # Mild blur: warn, but still pass to Qwen (it might extract something)
        issues.append(f"mild_blur (laplacian_var={blur_var:.1f})")
        if verdict == "pass":
            verdict = "warn"

    # Exposure evaluation — attempt CLAHE rescue in borderline-dark zone
    if mean < EXPOSURE_MIN * 0.6:
        issues.append(f"too_dark (mean={mean:.1f})")
        verdict = "reject"
        retake_reason = "Image is too dark. Use flash and retake."
    elif mean < CLAHE_TRIGGER_MEAN and blur_var >= BLUR_THRESHOLD:
        rescued = _apply_clahe(bgr)
        _, buf = cv2.imencode(".jpg", rescued, [cv2.IMWRITE_JPEG_QUALITY, 90])
        processed_bytes = buf.tobytes()
        issues.append("clahe_rescue_applied")
        _, exposure_norm = _exposure_score(cv2.cvtColor(rescued, cv2.COLOR_BGR2GRAY))
        if verdict == "pass":
            verdict = "warn"
    elif mean > EXPOSURE_MAX:
        issues.append(f"overexposed (mean={mean:.1f})")
        verdict = "reject"
        retake_reason = "Image is too bright or blown out. Move away from direct light."

    if not resolution_ok:
        verdict = "reject"
        retake_reason = retake_reason or "Image resolution is too low. Move closer."

    if not aspect_ratio_ok:
        verdict = "reject"
        retake_reason = retake_reason or "Unusual image shape. Use standard camera orientation."

    overall = float(0.5 * blur_norm + 0.3 * exposure_norm + 0.2 * (1.0 if resolution_ok else 0.0))

    return QualityResult(
        overall_score=round(overall, 3),
        blur_score=round(blur_norm, 3),
        exposure_score=round(exposure_norm, 3),
        resolution_ok=resolution_ok,
        aspect_ratio_ok=aspect_ratio_ok,
        verdict=verdict,
        issues=issues,
        retake_reason=retake_reason,
        content_hash=content_hash,
        width=w,
        height=h,
    ), processed_bytes
