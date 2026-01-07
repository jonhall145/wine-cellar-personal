"""
Grid detection module.

Uses calibrated rack bounds to analyze each cell and determine
if a bottle is present. Provides diff functionality to detect
which positions changed between two captures.
"""

import cv2
import numpy as np
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass

from .calibration import RackCalibrator


@dataclass
class CellState:
    """State of a single rack cell."""
    row: int
    col: int
    occupied: bool
    confidence: float  # 0.0 to 1.0
    # Debug info
    edge_density: float
    mean_intensity: float


@dataclass
class GridState:
    """Complete state of the rack grid."""
    cells: List[List[CellState]]
    timestamp: str
    image_hash: str  # For comparing if same image

    def get_occupied_positions(self) -> List[Tuple[int, int]]:
        """Get list of (row, col) for occupied cells."""
        positions = []
        for row in self.cells:
            for cell in row:
                if cell.occupied:
                    positions.append((cell.row, cell.col))
        return positions

    def to_bool_grid(self) -> List[List[bool]]:
        """Convert to simple boolean grid."""
        return [[cell.occupied for cell in row] for row in self.cells]


@dataclass
class GridDiff:
    """Difference between two grid states."""
    added: List[Tuple[int, int]]    # Positions where bottles were added
    removed: List[Tuple[int, int]]  # Positions where bottles were removed
    unchanged: List[Tuple[int, int]]  # Positions that didn't change


class GridDetector:
    """
    Detect bottle presence in rack cells.

    Uses the calibrated rack bounds to:
    1. Rectify the camera image
    2. Divide into grid cells
    3. Analyze each cell for bottle presence
    4. Compare states to detect changes
    """

    def __init__(
        self,
        calibrator: RackCalibrator,
        # Detection thresholds (tune based on your rack/lighting)
        edge_threshold: float = 0.08,
        intensity_threshold: float = 30.0,
    ):
        """
        Initialize grid detector.

        Args:
            calibrator: Calibrated RackCalibrator instance
            edge_threshold: Minimum edge density to consider cell occupied
            intensity_threshold: Minimum intensity variance for occupied cell
        """
        self.calibrator = calibrator
        self.edge_threshold = edge_threshold
        self.intensity_threshold = intensity_threshold

        # Reference empty cell (captured during calibration)
        self._empty_reference: Optional[np.ndarray] = None

    @property
    def rows(self) -> int:
        return self.calibrator.rows

    @property
    def columns(self) -> int:
        return self.calibrator.columns

    def set_empty_reference(self, image: np.ndarray) -> None:
        """
        Capture reference image of empty rack.

        This improves detection by comparing against known empty state.
        Call this once with an image of the completely empty rack.

        Args:
            image: Image of empty rack (will be rectified and stored)
        """
        self._empty_reference = self.calibrator.rectify_image(image)

    def analyze_grid(self, image: np.ndarray) -> GridState:
        """
        Analyze image and return grid state.

        Args:
            image: Camera image (BGR format)

        Returns:
            GridState with occupancy info for each cell
        """
        from datetime import datetime
        import hashlib

        if not self.calibrator.is_calibrated:
            raise RuntimeError("Calibrator must be calibrated first")

        # Rectify image
        rectified = self.calibrator.rectify_image(image)

        # Compute image hash for comparison
        img_hash = hashlib.md5(rectified.tobytes()).hexdigest()[:16]

        # Analyze each cell
        cells = []
        for r in range(self.rows):
            row_cells = []
            for c in range(self.columns):
                cell_state = self._analyze_cell(rectified, r, c)
                row_cells.append(cell_state)
            cells.append(row_cells)

        return GridState(
            cells=cells,
            timestamp=datetime.now().isoformat(),
            image_hash=img_hash,
        )

    def _analyze_cell(
        self,
        rectified: np.ndarray,
        row: int,
        col: int
    ) -> CellState:
        """
        Analyze a single cell for bottle presence.

        Uses multiple heuristics:
        1. Edge density - bottles have more edges than empty cells
        2. Intensity variance - bottles cause shadows/highlights
        3. Comparison to empty reference (if available)

        Args:
            rectified: Rectified rack image
            row: Cell row index
            col: Cell column index

        Returns:
            CellState with occupancy determination
        """
        x1, y1, x2, y2 = self.calibrator.get_cell_bounds(row, col)

        # Extract cell region
        cell_img = rectified[y1:y2, x1:x2]

        # Convert to grayscale
        gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)

        # Apply slight blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # 1. Edge detection
        edges = cv2.Canny(blurred, 30, 100)
        edge_density = np.sum(edges > 0) / edges.size

        # 2. Intensity analysis
        mean_intensity = np.mean(gray)
        intensity_std = np.std(gray)

        # 3. Compare to empty reference if available
        reference_diff = 0.0
        if self._empty_reference is not None:
            ref_cell = self._empty_reference[y1:y2, x1:x2]
            ref_gray = cv2.cvtColor(ref_cell, cv2.COLOR_BGR2GRAY)

            # Compute absolute difference
            diff = cv2.absdiff(gray, ref_gray)
            reference_diff = np.mean(diff)

        # Combine heuristics for final decision
        occupied = False
        confidence = 0.0

        # Primary: edge density
        if edge_density > self.edge_threshold:
            occupied = True
            confidence = min(edge_density / (self.edge_threshold * 2), 1.0)

        # Secondary: reference comparison (if available)
        if self._empty_reference is not None and reference_diff > 20:
            occupied = True
            confidence = max(confidence, reference_diff / 50)

        # Secondary: intensity variance
        if intensity_std > self.intensity_threshold:
            # Increase confidence but don't override
            confidence = min(confidence + 0.2, 1.0)

        return CellState(
            row=row,
            col=col,
            occupied=occupied,
            confidence=min(confidence, 1.0),
            edge_density=edge_density,
            mean_intensity=mean_intensity,
        )

    def compare_states(
        self,
        before: GridState,
        after: GridState
    ) -> GridDiff:
        """
        Compare two grid states to find changes.

        Args:
            before: Earlier grid state
            after: Later grid state

        Returns:
            GridDiff showing which positions changed
        """
        added = []
        removed = []
        unchanged = []

        for r in range(self.rows):
            for c in range(self.columns):
                was_occupied = before.cells[r][c].occupied
                is_occupied = after.cells[r][c].occupied

                if not was_occupied and is_occupied:
                    added.append((r, c))
                elif was_occupied and not is_occupied:
                    removed.append((r, c))
                else:
                    unchanged.append((r, c))

        return GridDiff(
            added=added,
            removed=removed,
            unchanged=unchanged,
        )

    def detect_single_change(
        self,
        before: GridState,
        after: GridState,
        expected_type: str = 'any'
    ) -> Optional[Tuple[int, int]]:
        """
        Detect a single bottle addition or removal.

        Useful for the workflow where we expect exactly one change.

        Args:
            before: State before action
            after: State after action
            expected_type: 'add', 'remove', or 'any'

        Returns:
            (row, col) of changed position, or None if not exactly one change
        """
        diff = self.compare_states(before, after)

        if expected_type == 'add':
            if len(diff.added) == 1 and len(diff.removed) == 0:
                return diff.added[0]
        elif expected_type == 'remove':
            if len(diff.removed) == 1 and len(diff.added) == 0:
                return diff.removed[0]
        else:  # 'any'
            if len(diff.added) == 1 and len(diff.removed) == 0:
                return diff.added[0]
            if len(diff.removed) == 1 and len(diff.added) == 0:
                return diff.removed[0]

        return None

    def draw_grid_overlay(
        self,
        image: np.ndarray,
        state: Optional[GridState] = None,
        highlight_cells: Optional[List[Tuple[int, int]]] = None,
        highlight_color: Tuple[int, int, int] = (0, 255, 255),
    ) -> np.ndarray:
        """
        Draw grid overlay on rectified image.

        Args:
            image: Camera image (will be rectified)
            state: Optional GridState to show occupancy
            highlight_cells: Optional list of (row, col) to highlight
            highlight_color: BGR color for highlighted cells

        Returns:
            Rectified image with grid overlay
        """
        rectified = self.calibrator.rectify_image(image)
        output = rectified.copy()
        w, h = self.calibrator.output_size

        # Draw grid lines
        cell_width = w // self.columns
        cell_height = h // self.rows

        # Vertical lines
        for c in range(self.columns + 1):
            x = c * cell_width
            cv2.line(output, (x, 0), (x, h), (255, 255, 255), 1)

        # Horizontal lines
        for r in range(self.rows + 1):
            y = r * cell_height
            cv2.line(output, (0, y), (w, y), (255, 255, 255), 1)

        # Draw cell labels and occupancy
        for r in range(self.rows):
            for c in range(self.columns):
                x1, y1, x2, y2 = self.calibrator.get_cell_bounds(r, c)
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2

                # Draw cell label
                label = f"{r},{c}"
                cv2.putText(
                    output, label, (x1 + 5, y1 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1
                )

                # Show occupancy if state provided
                if state:
                    cell = state.cells[r][c]
                    if cell.occupied:
                        # Green circle for occupied
                        cv2.circle(
                            output, (center_x, center_y),
                            min(cell_width, cell_height) // 4,
                            (0, 255, 0), 2
                        )
                        # Show confidence
                        conf_text = f"{cell.confidence:.0%}"
                        cv2.putText(
                            output, conf_text, (x1 + 5, y2 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1
                        )

                # Highlight specific cells
                if highlight_cells and (r, c) in highlight_cells:
                    cv2.rectangle(
                        output, (x1 + 2, y1 + 2), (x2 - 2, y2 - 2),
                        highlight_color, 3
                    )

        return output

    def get_cell_debug_info(
        self,
        image: np.ndarray,
        row: int,
        col: int
    ) -> Dict[str, Any]:
        """
        Get detailed debug info for a specific cell.

        Useful for tuning detection thresholds.

        Args:
            image: Camera image
            row: Cell row index
            col: Cell column index

        Returns:
            Dictionary with debug information
        """
        rectified = self.calibrator.rectify_image(image)
        x1, y1, x2, y2 = self.calibrator.get_cell_bounds(row, col)

        cell_img = rectified[y1:y2, x1:x2]
        gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 30, 100)

        info = {
            'row': row,
            'col': col,
            'bounds': (x1, y1, x2, y2),
            'edge_density': np.sum(edges > 0) / edges.size,
            'mean_intensity': float(np.mean(gray)),
            'intensity_std': float(np.std(gray)),
            'min_intensity': int(np.min(gray)),
            'max_intensity': int(np.max(gray)),
            'edge_threshold': self.edge_threshold,
            'intensity_threshold': self.intensity_threshold,
        }

        if self._empty_reference is not None:
            ref_cell = self._empty_reference[y1:y2, x1:x2]
            ref_gray = cv2.cvtColor(ref_cell, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(gray, ref_gray)
            info['reference_diff'] = float(np.mean(diff))

        return info
