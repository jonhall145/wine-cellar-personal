import logging
from typing import TYPE_CHECKING, Optional, Tuple, List

import cv2
import numpy as np
from PIL import Image, ImageEnhance

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Configuration constants
MIN_LABEL_AREA_RATIO = 0.05
MAX_LABEL_AREA_RATIO = 0.80  # Lowered: labels rarely take up 95% of a photo
MARGIN_PX = 3
# Kernel for morphological operations (adjust size based on typical image resolution)
MORPH_KERNEL_SIZE = (9, 9) 

def order_points(pts: "NDArray[np.floating]") -> "NDArray[np.floating]":
    """Order points: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def four_point_transform(image: "NDArray[np.uint8]", pts: "NDArray[np.floating]") -> "NDArray[np.uint8]":
    """Apply perspective transform."""
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    # Calculate width and height
    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    max_width = max(int(width_a), int(width_b))

    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    max_height = max(int(height_a), int(height_b))

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1]
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (max_width, max_height))

def auto_canny(image: "NDArray[np.uint8]", sigma: float = 0.33) -> "NDArray[np.uint8]":
    """Zero-parameter, automatic Canny edge detection."""
    v = np.median(image)
    lower = int(max(0, (1.0 - sigma) * v))
    upper = int(min(255, (1.0 + sigma) * v))
    return cv2.Canny(image, lower, upper)

def detect_label_contour(image: "NDArray[np.uint8]") -> Optional["NDArray[np.int32]"]:
    """
    Robust wine label detection using Morphological Gradients and MinAreaRect.
    """
    height, width = image.shape[:2]
    image_area = height * width
    image_center = (width // 2, height // 2)

    # 1. Preprocessing: Convert to Gray and apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    #    This is crucial for dark labels on dark bottles.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # 2. Blur to remove high frequency noise (dust/texture)
    blurred = cv2.bilateralFilter(gray, 9, 75, 75)

    # 3. Morphological Gradient
    #    This highlights the "structure" of the label (text blocks) better than simple edges.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, MORPH_KERNEL_SIZE)
    morph_grad = cv2.morphologyEx(blurred, cv2.MORPH_GRADIENT, kernel)

    # 4. Binarize using Otsu's thresholding
    #    This separates the "busy" label area from the "smooth" glass area.
    _, thresh = cv2.threshold(morph_grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 5. Morphological Closing
    #    This connects gaps. If there is glare cutting through the label, this fills it in.
    #    We use a wide rectangular kernel because text lines are horizontal.
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 5)) 
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, close_kernel, iterations=2)

    # 6. Find Contours
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    candidate_contours = []

    for c in contours:
        area = cv2.contourArea(c)
        if area / image_area < MIN_LABEL_AREA_RATIO:
            continue
            
        # 7. Use minAreaRect instead of approxPolyDP
        #    This finds the bounding box of the blob, even if the edges are jagged/curved.
        rect = cv2.minAreaRect(c)
        box = cv2.boxPoints(rect)
        box = box.astype(np.int32)
        
        # Calculate aspect ratio of the rect to ensure it's "label-shaped" (usually taller than wide)
        # Note: minAreaRect width/height order depends on angle, so we just check ratio of sides
        w, h = rect[1]
        if w == 0 or h == 0: continue
        aspect_ratio = min(w, h) / max(w, h)
        
        # Filter overly thin strips
        if aspect_ratio < 0.2: 
            continue

        candidate_contours.append((box, area))

    if not candidate_contours:
        return None

    # 8. Sort by a Score: Area + Centrality
    #    We prefer large contours that are close to the center of the image.
    def score_contour(candidate):
        box_pts, area = candidate
        # Calculate center of the box
        M = cv2.moments(box_pts)
        if M["m00"] == 0: return 0
        cX = int(M["m10"] / M["m00"])
        cY = int(M["m01"] / M["m00"])
        
        # Distance from image center (normalized)
        dist_x = abs(cX - image_center[0]) / width
        dist_y = abs(cY - image_center[1]) / height
        dist_penalty = (dist_x + dist_y)
        
        # Score = Area ratio - Distance Penalty
        # (We weight area higher, but penalize off-center boxes)
        return (area / image_area) - (dist_penalty * 0.5)

    # Get the candidate with the highest score
    best_candidate = max(candidate_contours, key=score_contour)
    return best_candidate[0]

def add_margin(image: "NDArray[np.uint8]", margin: int = MARGIN_PX) -> "NDArray[np.uint8]":
    """Add a white margin."""
    return cv2.copyMakeBorder(
        image, margin, margin, margin, margin,
        cv2.BORDER_CONSTANT, value=[255, 255, 255]
    )

def detect_and_crop_label(pil_image: Image.Image, target_height: int = 225) -> Tuple[Image.Image, bool]:
    """Detect label and create smart thumbnail."""
    if pil_image.mode not in ("RGB", "L"):
        pil_image = pil_image.convert("RGB")
    
    cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    try:
        label_contour = detect_label_contour(cv_image)

        if label_contour is not None:
            cropped = four_point_transform(cv_image, label_contour.astype("float32"))
            cropped = add_margin(cropped, MARGIN_PX)
            result = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
            
            # Resize
            aspect = result.width / result.height
            new_width = int(target_height * aspect)
            result = result.resize((new_width, target_height), Image.LANCZOS)
            
            return result, True

    except Exception as e:
        logger.warning(f"Label detection failed: {e}")

    # Fallback
    aspect = pil_image.width / pil_image.height
    new_width = int(target_height * aspect)
    fallback = pil_image.resize((new_width, target_height), Image.LANCZOS)
    return fallback, False

def enhance_detection_for_difficult_images(pil_image: Image.Image) -> Image.Image:
    """
    Enhance image for better label detection.
    Increases contrast and sharpness.
    """
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(pil_image)
    img = enhancer.enhance(1.5)

    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.5)

    return img