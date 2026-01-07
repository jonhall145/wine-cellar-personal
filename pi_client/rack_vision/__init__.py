"""
Rack vision system for wine cellar bottle position detection.

This module provides:
- One-time rack calibration (detect rack bounds)
- Grid overlay computation from calibrated bounds
- Bottle presence detection per cell
- Before/after diff to detect position changes
"""

from .calibration import RackCalibrator
from .grid_detector import GridDetector
from .bottle_detector import BottleDetector

__all__ = ['RackCalibrator', 'GridDetector', 'BottleDetector']
