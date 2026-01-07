"""
Rack calibration module.

Handles one-time calibration to detect rack bounds in the camera frame.
Since the rack is fixed, calibration only needs to be done once (or when
the camera position changes).

The calibration stores:
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
