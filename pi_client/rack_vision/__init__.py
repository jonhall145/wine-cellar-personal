"""
Rack vision system for wine cellar bottle position detection.

This module provides:
- Auto-detecting rack calibration (recommended - detects corners each frame)
- Manual one-time calibration (fallback)
- ArUco marker-based calibration (most reliable)
- Grid overlay computation from detected bounds
- Bottle presence detection per cell
- Before/after diff to detect position changes

Calibration Options:
1. AutoDetectingCalibrator - Detects rack corners in every frame
   - Most flexible, handles camera movement
   - No manual setup required
   - Works if rack has visible edges

2. MarkerBasedCalibrator - Uses ArUco markers at rack corners
   - Most reliable detection
   - Requires printing and attaching 4 markers
   - Use generate_markers() to create marker images

3. RackCalibrator - Manual one-time calibration
   - Click 4 corners once
   - Requires camera to stay perfectly still
"""

from .calibration import (
    RackCalibrator,
    AutoDetectingCalibrator,
    MarkerBasedCalibrator,
)
from .grid_detector import GridDetector
from .bottle_detector import BottleDetector

__all__ = [
    'RackCalibrator',
    'AutoDetectingCalibrator',
    'MarkerBasedCalibrator',
    'GridDetector',
    'BottleDetector',
]
