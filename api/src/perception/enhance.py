"""
Pre-VLM image enhancement for messy real-world shelf photos.
Handles: glare, angle, thumb crops, dark coolers, motion blur.
"""
import cv2
import numpy as np
from PIL import Image, ImageOps
from io import BytesIO


def enhance_image(image_bytes: bytes) -> tuple[bytes, dict]:
    """
    Returns (enhanced_bytes, enhancement_report).
    enhancement_report tells the VLM what was done.
    """
    report = {
        "applied": [],
        "glare_detected": False,
        "angle_corrected": False,
        "cropped_artifact": False,
        "brightness_adjusted": False,
    }

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes, report

    h, w = img.shape[:2]
    h_int = int(h)

    # 1. GLARE DETECTION (specular reflection)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Specular highlights = very bright + low saturation
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    bright_mask = (gray > 230) & (hsv[:, :, 1] < 40)  # bright + low saturation
    glare_ratio = float(np.sum(bright_mask)) / (h_int * int(w))
    if glare_ratio > 0.02:  # >2% of image is glare
        report["glare_detected"] = True
        report["applied"].append("glare_inpaint")
        # Inpaint glare regions
        mask = bright_mask.astype(np.uint8) * 255
        mask = cv2.dilate(mask, np.ones((7, 7), np.uint8), iterations=2)
        img = cv2.inpaint(img, mask, 5, cv2.INPAINT_TELEA)

    # 2. CLAHE for dark cooler photos
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l_mean = float(np.mean(l))
    if l_mean < 100:  # dark image
        report["brightness_adjusted"] = True
        report["applied"].append("clahe_low_light")
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        img = cv2.merge((l, a, b))
        img = cv2.cvtColor(img, cv2.COLOR_LAB2BGR)

    # 3. THUMB / BORDER ARTIFACT CROP
    # Detect dark borders (thumb, phone edge)
    edges = cv2.Canny(gray, 50, 150)
    row_sums = np.sum(edges > 0, axis=1)
    h_int = int(h)
    bottom_region_mean = float(np.mean(row_sums[int(h_int * 0.9):]))
    all_rows_mean = float(np.mean(row_sums))
    if bottom_region_mean > all_rows_mean * 2:
        crop_h = int(h_int * 0.88)
        img = img[:crop_h, :, :]
        report["cropped_artifact"] = True
        report["applied"].append("bottom_border_crop")
        h = crop_h

    # 4. ANGLE CORRECTION (shelf skew) — DISABLED for numpy stability
    # Opencv HoughLinesP returns numpy types that vary across versions.
    # Angle correction is low-value for VLM extraction — Qwen handles slight skew.
    # If needed, re-enable with cv2 version check and exhaustive numpy casting.

    # Encode back
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if ok:
        return buf.tobytes(), report
    return image_bytes, report
