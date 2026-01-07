"""
Rack calibration module.

Supports two modes:
1. AUTO-DETECT (recommended): Detect rack corners in every frame
   - Robust to small camera movements
   - No manual calibration needed
   - Self-correcting

2. MANUAL (fallback): One-time corner selection
   - For racks that are hard to auto-detect
   - Requires re-calibration if camera moves

The calibration provides:
- Four corner points of the rack in image coordinates
- Grid dimensions (rows x columns)
- Perspective transform matrix for rectification
"""

import json
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List


class RackCalibrator:
    """
    Calibrate camera view to detect fixed rack bounds.

    The rack bounds define the region of interest and enable:
    - Perspective correction for angled camera views
    - Consistent grid overlay regardless of camera angle
    - Accurate cell-to-position mapping
    """

    CONFIG_DIR = Path('/etc/wine-cellar')

    def __init__(self, storage_id: int, rows: int, columns: int):
        """
        Initialize calibrator for a specific storage rack.

        Args:
            storage_id: Database ID of the storage rack
            rows: Number of rows in the rack
            columns: Number of columns in the rack
        """
        self.storage_id = storage_id
        self.rows = rows
        self.columns = columns
        self.corners: Optional[np.ndarray] = None  # 4 corner points
        self.transform_matrix: Optional[np.ndarray] = None
        self.output_size: Tuple[int, int] = (800, 600)  # Rectified image size

        # Try to load existing calibration
        self._load_calibration()

    @property
    def config_path(self) -> Path:
        """Path to calibration config file."""
        return self.CONFIG_DIR / f'calibration_{self.storage_id}.json'

    @property
    def is_calibrated(self) -> bool:
        """Check if calibration data exists."""
        return self.corners is not None and self.transform_matrix is not None

    def _load_calibration(self) -> bool:
        """Load calibration from config file if exists."""
        if not self.config_path.exists():
            return False

        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)

            self.corners = np.array(data['corners'], dtype=np.float32)
            self.rows = data['rows']
            self.columns = data['columns']
            self.output_size = tuple(data['output_size'])

            # Recompute transform matrix
            self._compute_transform()
            return True

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Failed to load calibration: {e}")
            return False

    def save_calibration(self) -> bool:
        """Save calibration to config file."""
        if not self.is_calibrated:
            return False

        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        data = {
            'storage_id': self.storage_id,
            'corners': self.corners.tolist(),
            'rows': self.rows,
            'columns': self.columns,
            'output_size': list(self.output_size),
            'calibrated_at': datetime.now().isoformat(),
        }

        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)

        return True

    def set_corners_manual(self, corners: List[Tuple[int, int]]) -> None:
        """
        Manually set the four corners of the rack.

        Args:
            corners: List of 4 (x, y) tuples in order:
                     [top-left, top-right, bottom-right, bottom-left]
        """
        if len(corners) != 4:
            raise ValueError("Must provide exactly 4 corner points")

        self.corners = np.array(corners, dtype=np.float32)
        self._compute_transform()
        self.save_calibration()

    def detect_corners_auto(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Attempt to auto-detect rack corners from image.

        This uses edge detection and contour finding to locate
        the rectangular rack region. Works best with good contrast
        between rack and background.

        Args:
            image: BGR image from camera

        Returns:
            Detected corners or None if detection failed
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Edge detection
        edges = cv2.Canny(blurred, 50, 150)

        # Dilate to connect nearby edges
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return None

        # Find the largest rectangular contour (likely the rack)
        largest_rect = None
        largest_area = 0

        for contour in contours:
            # Approximate contour to polygon
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            # Look for quadrilaterals
            if len(approx) == 4:
                area = cv2.contourArea(approx)
                if area > largest_area:
                    largest_area = area
                    largest_rect = approx

        if largest_rect is None:
            return None

        # Order corners: top-left, top-right, bottom-right, bottom-left
        corners = self._order_corners(largest_rect.reshape(4, 2))

        return corners

    def _order_corners(self, pts: np.ndarray) -> np.ndarray:
        """
        Order corner points consistently.

        Returns points in order: top-left, top-right, bottom-right, bottom-left
        """
        # Sort by y-coordinate (top vs bottom)
        sorted_by_y = pts[np.argsort(pts[:, 1])]

        # Top two points
        top = sorted_by_y[:2]
        top = top[np.argsort(top[:, 0])]  # Sort by x (left to right)

        # Bottom two points
        bottom = sorted_by_y[2:]
        bottom = bottom[np.argsort(bottom[:, 0])]  # Sort by x (left to right)

        return np.array([
            top[0],      # top-left
            top[1],      # top-right
            bottom[1],   # bottom-right
            bottom[0],   # bottom-left
        ], dtype=np.float32)

    def _compute_transform(self) -> None:
        """Compute perspective transform matrix from corners."""
        if self.corners is None:
            return

        # Destination points (rectified rectangle)
        w, h = self.output_size
        dst_corners = np.array([
            [0, 0],
            [w - 1, 0],
            [w - 1, h - 1],
            [0, h - 1],
        ], dtype=np.float32)

        self.transform_matrix = cv2.getPerspectiveTransform(
            self.corners, dst_corners
        )

    def rectify_image(self, image: np.ndarray) -> np.ndarray:
        """
        Apply perspective transform to get rectified (flat) view.

        Args:
            image: Original camera image

        Returns:
            Rectified image with rack as flat rectangle
        """
        if not self.is_calibrated:
            raise RuntimeError("Calibration required before rectification")

        return cv2.warpPerspective(
            image,
            self.transform_matrix,
            self.output_size
        )

    def get_cell_bounds(self, row: int, col: int) -> Tuple[int, int, int, int]:
        """
        Get pixel bounds for a specific cell in rectified image.

        Args:
            row: Row index (0-based)
            col: Column index (0-based)

        Returns:
            Tuple of (x1, y1, x2, y2) pixel coordinates
        """
        w, h = self.output_size
        cell_width = w // self.columns
        cell_height = h // self.rows

        x1 = col * cell_width
        y1 = row * cell_height
        x2 = x1 + cell_width
        y2 = y1 + cell_height

        return (x1, y1, x2, y2)

    def get_all_cell_bounds(self) -> List[List[Tuple[int, int, int, int]]]:
        """
        Get pixel bounds for all cells.

        Returns:
            2D list of cell bounds [row][col] = (x1, y1, x2, y2)
        """
        return [
            [self.get_cell_bounds(r, c) for c in range(self.columns)]
            for r in range(self.rows)
        ]

    def draw_calibration_overlay(self, image: np.ndarray) -> np.ndarray:
        """
        Draw calibration overlay on image for verification.

        Args:
            image: Original camera image

        Returns:
            Image with overlay showing detected corners and grid
        """
        output = image.copy()

        if self.corners is not None:
            # Draw corner points
            for i, corner in enumerate(self.corners):
                pt = tuple(corner.astype(int))
                cv2.circle(output, pt, 10, (0, 255, 0), -1)
                cv2.putText(
                    output, str(i), pt,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2
                )

            # Draw rack outline
            pts = self.corners.astype(int).reshape((-1, 1, 2))
            cv2.polylines(output, [pts], True, (0, 255, 0), 2)

            # Draw grid lines (projected onto original perspective)
            if self.transform_matrix is not None:
                inv_transform = cv2.invert(self.transform_matrix)[1]
                w, h = self.output_size

                # Vertical lines
                for c in range(1, self.columns):
                    x = c * (w // self.columns)
                    pt1 = self._transform_point(inv_transform, (x, 0))
                    pt2 = self._transform_point(inv_transform, (x, h - 1))
                    cv2.line(output, pt1, pt2, (255, 255, 0), 1)

                # Horizontal lines
                for r in range(1, self.rows):
                    y = r * (h // self.rows)
                    pt1 = self._transform_point(inv_transform, (0, y))
                    pt2 = self._transform_point(inv_transform, (w - 1, y))
                    cv2.line(output, pt1, pt2, (255, 255, 0), 1)

        return output

    def _transform_point(
        self, matrix: np.ndarray, point: Tuple[int, int]
    ) -> Tuple[int, int]:
        """Transform a single point using perspective matrix."""
        pt = np.array([[point]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, matrix)
        return tuple(transformed[0][0].astype(int))


# Interactive calibration helper for command-line use
def interactive_calibration(
    camera,
    storage_id: int,
    rows: int,
    columns: int
) -> RackCalibrator:
    """
    Interactive calibration using mouse clicks.

    Args:
        camera: Camera object with capture() method
        storage_id: Database ID of the storage rack
        rows: Number of rows in the rack
        columns: Number of columns in the rack

    Returns:
        Calibrated RackCalibrator instance
    """
    calibrator = RackCalibrator(storage_id, rows, columns)
    corners = []

    def mouse_callback(event, x, y, flags, param):
        nonlocal corners
        if event == cv2.EVENT_LBUTTONDOWN and len(corners) < 4:
            corners.append((x, y))
            print(f"Corner {len(corners)}: ({x}, {y})")

    # Capture frame
    frame = camera.capture()

    cv2.namedWindow('Calibration')
    cv2.setMouseCallback('Calibration', mouse_callback)

    print("Click the 4 corners of the rack in order:")
    print("1. Top-left")
    print("2. Top-right")
    print("3. Bottom-right")
    print("4. Bottom-left")
    print("Press 'r' to reset, 'q' to quit, Enter to confirm")

    while True:
        display = frame.copy()

        # Draw clicked corners
        for i, corner in enumerate(corners):
            cv2.circle(display, corner, 8, (0, 255, 0), -1)
            cv2.putText(
                display, str(i + 1), corner,
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
            )

        # Draw lines between corners
        if len(corners) >= 2:
            for i in range(len(corners) - 1):
                cv2.line(display, corners[i], corners[i + 1], (0, 255, 0), 2)
            if len(corners) == 4:
                cv2.line(display, corners[3], corners[0], (0, 255, 0), 2)

        cv2.imshow('Calibration', display)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('r'):
            corners = []
            print("Reset corners")
        elif key == ord('q'):
            break
        elif key == 13 and len(corners) == 4:  # Enter key
            calibrator.set_corners_manual(corners)
            print("Calibration saved!")
            break

    cv2.destroyAllWindows()
    return calibrator


class AutoDetectingCalibrator:
    """
    Automatically detect rack corners on every frame.

    This is more robust than one-time calibration because:
    - Handles small camera movements between captures
    - No manual calibration needed
    - Self-correcting if rack shifts slightly

    The rack structure itself serves as the reference. Detection works by:
    1. Finding the largest rectangular contour (the rack)
    2. Extracting the 4 corners
    3. Computing perspective transform
    4. Applying grid overlay

    For best results:
    - Rack should have clear edges visible against background
    - Good contrast between rack and wall/floor
    - Consistent lighting
    """

    def __init__(
        self,
        rows: int,
        columns: int,
        output_size: Tuple[int, int] = (800, 600),
        min_rack_area_ratio: float = 0.1,
        use_reference: bool = True,
    ):
        """
        Initialize auto-detecting calibrator.

        Args:
            rows: Number of rows in the rack
            columns: Number of columns in the rack
            output_size: Size of rectified output image (width, height)
            min_rack_area_ratio: Minimum rack area as ratio of image area
            use_reference: If True, use first successful detection as reference
                          for more stable subsequent detections
        """
        self.rows = rows
        self.columns = columns
        self.output_size = output_size
        self.min_rack_area_ratio = min_rack_area_ratio
        self.use_reference = use_reference

        # Reference corners from first successful detection
        self._reference_corners: Optional[np.ndarray] = None

        # Last detected corners (for debugging/display)
        self._last_corners: Optional[np.ndarray] = None
        self._last_transform: Optional[np.ndarray] = None

    def detect_corners(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect rack corners in the given image.

        Args:
            image: BGR image from camera

        Returns:
            4 corner points as numpy array, or None if detection failed
            Order: [top-left, top-right, bottom-right, bottom-left]
        """
        h, w = image.shape[:2]
        min_area = w * h * self.min_rack_area_ratio

        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply bilateral filter to reduce noise while keeping edges
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)

        # Adaptive thresholding for better edge detection in varying lighting
        thresh = cv2.adaptiveThreshold(
            filtered, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        # Edge detection
        edges = cv2.Canny(filtered, 30, 100)

        # Dilate to connect nearby edges
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return self._fallback_to_reference()

        # Find the largest quadrilateral contour
        best_corners = None
        best_area = 0

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue

            # Approximate contour to polygon
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            # Look for quadrilaterals
            if len(approx) == 4 and area > best_area:
                # Check if it's convex (a proper rectangle)
                if cv2.isContourConvex(approx):
                    best_area = area
                    best_corners = approx.reshape(4, 2)

        if best_corners is None:
            return self._fallback_to_reference()

        # Order corners consistently
        corners = self._order_corners(best_corners)

        # Validate corners make sense (roughly rectangular)
        if not self._validate_corners(corners, w, h):
            return self._fallback_to_reference()

        # Update reference if this is first detection or significantly better
        if self.use_reference:
            if self._reference_corners is None:
                self._reference_corners = corners.copy()
            else:
                # Only update reference if very close to current reference
                # This prevents drift from accumulated small errors
                diff = np.linalg.norm(corners - self._reference_corners)
                if diff < 50:  # pixels
                    # Smooth update
                    self._reference_corners = (
                        0.9 * self._reference_corners + 0.1 * corners
                    )

        self._last_corners = corners
        return corners

    def _fallback_to_reference(self) -> Optional[np.ndarray]:
        """Fall back to reference corners if detection fails."""
        if self._reference_corners is not None:
            self._last_corners = self._reference_corners
            return self._reference_corners.copy()
        return None

    def _order_corners(self, pts: np.ndarray) -> np.ndarray:
        """Order corners: top-left, top-right, bottom-right, bottom-left."""
        # Sort by y-coordinate
        sorted_by_y = pts[np.argsort(pts[:, 1])]

        # Top two points (sorted by x)
        top = sorted_by_y[:2]
        top = top[np.argsort(top[:, 0])]

        # Bottom two points (sorted by x)
        bottom = sorted_by_y[2:]
        bottom = bottom[np.argsort(bottom[:, 0])]

        return np.array([
            top[0],      # top-left
            top[1],      # top-right
            bottom[1],   # bottom-right
            bottom[0],   # bottom-left
        ], dtype=np.float32)

    def _validate_corners(
        self,
        corners: np.ndarray,
        img_width: int,
        img_height: int
    ) -> bool:
        """Validate that corners form a reasonable rectangle."""
        # Check all corners are within image bounds
        for corner in corners:
            if not (0 <= corner[0] < img_width and 0 <= corner[1] < img_height):
                return False

        # Check aspect ratio is reasonable (not too skewed)
        width_top = np.linalg.norm(corners[1] - corners[0])
        width_bottom = np.linalg.norm(corners[2] - corners[3])
        height_left = np.linalg.norm(corners[3] - corners[0])
        height_right = np.linalg.norm(corners[2] - corners[1])

        # Widths should be similar
        if max(width_top, width_bottom) / (min(width_top, width_bottom) + 1) > 1.5:
            return False

        # Heights should be similar
        if max(height_left, height_right) / (min(height_left, height_right) + 1) > 1.5:
            return False

        return True

    def rectify_image(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect corners and rectify image in one step.

        Args:
            image: Camera image (BGR)

        Returns:
            Rectified image, or None if corner detection failed
        """
        corners = self.detect_corners(image)
        if corners is None:
            return None

        # Destination points (rectified rectangle)
        w, h = self.output_size
        dst_corners = np.array([
            [0, 0],
            [w - 1, 0],
            [w - 1, h - 1],
            [0, h - 1],
        ], dtype=np.float32)

        self._last_transform = cv2.getPerspectiveTransform(corners, dst_corners)

        return cv2.warpPerspective(
            image,
            self._last_transform,
            self.output_size
        )

    def get_cell_bounds(self, row: int, col: int) -> Tuple[int, int, int, int]:
        """Get pixel bounds for a cell in the rectified image."""
        w, h = self.output_size
        cell_width = w // self.columns
        cell_height = h // self.rows

        x1 = col * cell_width
        y1 = row * cell_height
        x2 = x1 + cell_width
        y2 = y1 + cell_height

        return (x1, y1, x2, y2)

    def draw_detection_overlay(self, image: np.ndarray) -> np.ndarray:
        """
        Draw detected corners and grid overlay on image.

        Useful for debugging and visualizing detection quality.
        """
        output = image.copy()

        if self._last_corners is not None:
            corners = self._last_corners

            # Draw corner points with labels
            labels = ['TL', 'TR', 'BR', 'BL']
            colors = [(0, 255, 0), (0, 255, 255), (255, 0, 0), (255, 0, 255)]

            for i, (corner, label, color) in enumerate(zip(corners, labels, colors)):
                pt = tuple(corner.astype(int))
                cv2.circle(output, pt, 8, color, -1)
                cv2.putText(
                    output, label, (pt[0] + 10, pt[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
                )

            # Draw rack outline
            pts = corners.astype(int).reshape((-1, 1, 2))
            cv2.polylines(output, [pts], True, (0, 255, 0), 2)

            # Draw grid lines if we have a transform
            if self._last_transform is not None:
                inv_transform = cv2.invert(self._last_transform)[1]
                w, h = self.output_size

                # Vertical lines
                for c in range(1, self.columns):
                    x = c * (w // self.columns)
                    pt1 = self._transform_point(inv_transform, (x, 0))
                    pt2 = self._transform_point(inv_transform, (x, h - 1))
                    cv2.line(output, pt1, pt2, (255, 255, 0), 1)

                # Horizontal lines
                for r in range(1, self.rows):
                    y = r * (h // self.rows)
                    pt1 = self._transform_point(inv_transform, (0, y))
                    pt2 = self._transform_point(inv_transform, (w - 1, y))
                    cv2.line(output, pt1, pt2, (255, 255, 0), 1)

        # Show detection status
        status = "DETECTED" if self._last_corners is not None else "NOT FOUND"
        color = (0, 255, 0) if self._last_corners is not None else (0, 0, 255)
        cv2.putText(
            output, f"Rack: {status}",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2
        )

        return output

    def _transform_point(
        self, matrix: np.ndarray, point: Tuple[int, int]
    ) -> Tuple[int, int]:
        """Transform a single point using perspective matrix."""
        pt = np.array([[point]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, matrix)
        return tuple(transformed[0][0].astype(int))

    def reset_reference(self) -> None:
        """Clear reference corners to force fresh detection."""
        self._reference_corners = None
        self._last_corners = None
        self._last_transform = None


class MarkerBasedCalibrator:
    """
    Use ArUco markers for precise rack corner detection.

    Place 4 ArUco markers at the corners of the rack for
    extremely reliable detection. This is the most robust method
    but requires printing and attaching markers.

    Marker IDs expected:
    - ID 0: Top-left
    - ID 1: Top-right
    - ID 2: Bottom-right
    - ID 3: Bottom-left
    """

    def __init__(
        self,
        rows: int,
        columns: int,
        output_size: Tuple[int, int] = (800, 600),
        dictionary: int = cv2.aruco.DICT_4X4_50,
    ):
        """
        Initialize marker-based calibrator.

        Args:
            rows: Number of rows in the rack
            columns: Number of columns in the rack
            output_size: Size of rectified output image
            dictionary: ArUco dictionary to use
        """
        self.rows = rows
        self.columns = columns
        self.output_size = output_size

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)

        self._last_corners: Optional[np.ndarray] = None
        self._last_transform: Optional[np.ndarray] = None

    def detect_corners(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect rack corners using ArUco markers.

        Args:
            image: BGR image from camera

        Returns:
            4 corner points, or None if not all markers found
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        corners, ids, _ = self.detector.detectMarkers(gray)

        if ids is None or len(ids) < 4:
            return None

        # Find markers 0, 1, 2, 3
        marker_corners = {}
        for i, marker_id in enumerate(ids.flatten()):
            if marker_id in [0, 1, 2, 3]:
                # Use center of marker
                marker_corners[marker_id] = corners[i][0].mean(axis=0)

        if len(marker_corners) < 4:
            return None

        # Build corner array in order
        rack_corners = np.array([
            marker_corners[0],  # top-left
            marker_corners[1],  # top-right
            marker_corners[2],  # bottom-right
            marker_corners[3],  # bottom-left
        ], dtype=np.float32)

        self._last_corners = rack_corners
        return rack_corners

    def rectify_image(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Detect markers and rectify image."""
        corners = self.detect_corners(image)
        if corners is None:
            return None

        w, h = self.output_size
        dst_corners = np.array([
            [0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]
        ], dtype=np.float32)

        self._last_transform = cv2.getPerspectiveTransform(corners, dst_corners)
        return cv2.warpPerspective(image, self._last_transform, self.output_size)

    def get_cell_bounds(self, row: int, col: int) -> Tuple[int, int, int, int]:
        """Get pixel bounds for a cell in the rectified image."""
        w, h = self.output_size
        cell_width = w // self.columns
        cell_height = h // self.rows
        return (col * cell_width, row * cell_height,
                (col + 1) * cell_width, (row + 1) * cell_height)

    @staticmethod
    def generate_markers(output_dir: str = '.', size: int = 200) -> None:
        """
        Generate ArUco marker images to print.

        Args:
            output_dir: Directory to save marker images
            size: Size of markers in pixels
        """
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

        for marker_id in range(4):
            marker = cv2.aruco.generateImageMarker(dictionary, marker_id, size)
            filename = f"{output_dir}/aruco_marker_{marker_id}.png"
            cv2.imwrite(filename, marker)
            print(f"Saved {filename}")

        print("\nPrint these markers and place at rack corners:")
        print("- Marker 0: Top-left")
        print("- Marker 1: Top-right")
        print("- Marker 2: Bottom-right")
        print("- Marker 3: Bottom-left")
