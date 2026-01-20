"""
Smart wine label detection and cropping using OpenCV.

Algorithm:
1. Convert to grayscale
2. Apply bilateral filter (preserves edges while smoothing)
3. Canny edge detection
4. Find contours
5. Filter for rectangular contours (label candidates)
6. Select largest rectangular contour
7. Apply perspective transform if skewed
8. Crop with 3px margin
"""

import logging
from typing import TYPE_CHECKING, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Configuration constants
CANNY_LOW_THRESHOLD = 50
CANNY_HIGH_THRESHOLD = 150
MIN_LABEL_AREA_RATIO = 0.05  # Label must be at least 5% of image
MAX_LABEL_AREA_RATIO = 0.95  # Label can't be more than 95% of image
MARGIN_PX = 3
BILATERAL_D = 9
BILATERAL_SIGMA_COLOR = 75
BILATERAL_SIGMA_SPACE = 75


def order_points(pts: "NDArray[np.floating]") -> "NDArray[np.floating]":
    """
    Order points in: top-left, top-right, bottom-right, bottom-left order.
    Required for perspective transform.
    """
    rect = np.zeros((4, 2), dtype="float32")

    # Sum of coordinates: top-left has smallest sum, bottom-right has largest
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # Difference of coordinates: top-right has smallest diff, bottom-left has largest
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


def four_point_transform(
    image: "NDArray[np.uint8]", pts: "NDArray[np.floating]"
) -> "NDArray[np.uint8]":
    """
    Apply perspective transform to obtain a top-down view of the label.
    """
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    # Compute width of new image (max of top and bottom edge widths)
    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    max_width = max(int(width_a), int(width_b))

    # Compute height of new image (max of left and right edge heights)
    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    max_height = max(int(height_a), int(height_b))

    # Destination points for "birds eye view"
    dst = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype="float32",
    )

    # Compute perspective transform matrix and apply
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (max_width, max_height))

    return warped


def detect_label_contour(image: "NDArray[np.uint8]") -> Optional["NDArray[np.int32]"]:
    """
    Detect the wine label contour using edge detection.

    Returns:
        4-point contour array if found, None otherwise
    """
    height, width = image.shape[:2]
    image_area = height * width

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply bilateral filter to reduce noise while keeping edges sharp
    blurred = cv2.bilateralFilter(
        gray,
        BILATERAL_D,
        BILATERAL_SIGMA_COLOR,
        BILATERAL_SIGMA_SPACE,
    )

    # Canny edge detection
    edges = cv2.Canny(blurred, CANNY_LOW_THRESHOLD, CANNY_HIGH_THRESHOLD)

    # Dilate edges to close gaps
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    # Sort by area descending
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for contour in contours[:10]:  # Check top 10 largest contours
        # Approximate the contour
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

        # Check if it's a quadrilateral
        if len(approx) == 4:
            area = cv2.contourArea(approx)
            area_ratio = area / image_area

            # Validate area is reasonable for a label
            if MIN_LABEL_AREA_RATIO < area_ratio < MAX_LABEL_AREA_RATIO:
                return approx.reshape(4, 2)

    return None


def add_margin(
    image: "NDArray[np.uint8]", margin: int = MARGIN_PX
) -> "NDArray[np.uint8]":
    """
    Add a white margin around the cropped image.
    """
    return cv2.copyMakeBorder(
        image,
        margin,
        margin,
        margin,
        margin,
        cv2.BORDER_CONSTANT,
        value=[255, 255, 255],  # White margin
    )


def detect_and_crop_label(
    pil_image: Image.Image,
    target_height: int = 225,
) -> Tuple[Image.Image, bool]:
    """
    Main entry point: detect label and create smart thumbnail.

    Args:
        pil_image: PIL Image to process
        target_height: Target height for thumbnail

    Returns:
        Tuple of (processed PIL Image, success boolean)
        If detection fails, returns scaled original with False
    """
    # Convert to RGB if needed
    if pil_image.mode not in ("RGB", "L"):
        pil_image = pil_image.convert("RGB")

    # Convert PIL to OpenCV format (RGB -> BGR)
    cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    try:
        # Detect label contour
        label_contour = detect_label_contour(cv_image)

        if label_contour is not None:
            # Apply perspective transform to get straight label
            cropped = four_point_transform(cv_image, label_contour.astype("float32"))

            # Add 3px margin
            cropped = add_margin(cropped, MARGIN_PX)

            # Convert back to PIL (BGR -> RGB)
            result = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))

            # Resize to target height maintaining aspect ratio
            aspect = result.width / result.height
            new_width = int(target_height * aspect)
            result = result.resize((new_width, target_height), Image.LANCZOS)

            logger.info("Label detection successful")
            return result, True

    except Exception as e:
        logger.warning(f"Label detection failed: {e}")

    # Fallback: return scaled original
    logger.info("Using fallback thumbnail (no label detected)")
    aspect = pil_image.width / pil_image.height
    new_width = int(target_height * aspect)
    fallback = pil_image.resize((new_width, target_height), Image.LANCZOS)
    return fallback, False


def enhance_detection_for_difficult_images(pil_image: Image.Image) -> Image.Image:
    """
    Apply preprocessing for images with poor lighting or low contrast.
    Called as fallback when initial detection fails.
    """
    # Convert to RGB if needed
    if pil_image.mode not in ("RGB", "L"):
        pil_image = pil_image.convert("RGB")

    cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    lab = cv2.cvtColor(cv_image, cv2.COLOR_BGR2LAB)
    l_channel, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    enhanced = cv2.merge([l_channel, a, b])
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    return Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB))
