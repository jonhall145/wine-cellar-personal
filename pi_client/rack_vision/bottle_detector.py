"""
Bottle detector module.

Combines barcode scanning with grid detection to provide
a complete bottle detection workflow.
"""

import cv2
import numpy as np
from typing import Optional, List, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime

try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False


@dataclass
class BarcodeResult:
    """Result of barcode detection."""
    barcode: str
    barcode_type: str
    confidence: float
    bounding_box: Tuple[int, int, int, int]  # x, y, w, h
    timestamp: str


class BottleDetector:
    """
    Detect bottles via barcode scanning using camera.

    Uses continuous frame analysis to detect barcodes without
    requiring a button press. Detection is debounced to avoid
    multiple triggers for the same barcode.
    """

    # Supported barcode formats
    SUPPORTED_FORMATS = [
        'EAN13', 'EAN8', 'UPCA', 'UPCE',
        'CODE39', 'CODE93', 'CODE128', 'ITF',
    ]

    def __init__(
        self,
        debounce_seconds: float = 2.0,
        min_confidence: float = 0.5,
    ):
        """
        Initialize bottle detector.

        Args:
            debounce_seconds: Minimum time between same barcode detections
            min_confidence: Minimum confidence to accept detection
        """
        if not PYZBAR_AVAILABLE:
            raise ImportError(
                "pyzbar not installed. Run: pip install pyzbar\n"
                "Also install system library: sudo apt-get install libzbar0"
            )

        self.debounce_seconds = debounce_seconds
        self.min_confidence = min_confidence

        # Track recent detections for debouncing
        self._last_detections: dict = {}  # barcode -> timestamp

        # Callback for barcode detection
        self._on_barcode: Optional[Callable[[BarcodeResult], None]] = None

    def set_barcode_callback(
        self,
        callback: Callable[[BarcodeResult], None]
    ) -> None:
        """
        Set callback for barcode detection.

        Args:
            callback: Function called with BarcodeResult when barcode detected
        """
        self._on_barcode = callback

    def scan_frame(self, frame: np.ndarray) -> Optional[BarcodeResult]:
        """
        Scan a single frame for barcodes.

        Args:
            frame: BGR image from camera

        Returns:
            BarcodeResult if new barcode detected, None otherwise
        """
        # Convert to grayscale for better detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Decode barcodes
        barcodes = pyzbar.decode(gray)

        if not barcodes:
            return None

        # Take the first barcode (could extend to handle multiple)
        barcode = barcodes[0]

        # Extract data
        barcode_data = barcode.data.decode('utf-8')
        barcode_type = barcode.type

        # Check if it's a supported format
        if barcode_type not in self.SUPPORTED_FORMATS:
            return None

        # Check debounce
        now = datetime.now()
        if barcode_data in self._last_detections:
            last_time = self._last_detections[barcode_data]
            elapsed = (now - last_time).total_seconds()
            if elapsed < self.debounce_seconds:
                return None

        # Update last detection time
        self._last_detections[barcode_data] = now

        # Build result
        x, y, w, h = barcode.rect
        result = BarcodeResult(
            barcode=barcode_data,
            barcode_type=barcode_type,
            confidence=1.0,  # pyzbar doesn't provide confidence
            bounding_box=(x, y, w, h),
            timestamp=now.isoformat(),
        )

        # Trigger callback if set
        if self._on_barcode:
            self._on_barcode(result)

        return result

    def scan_continuous(
        self,
        camera,
        timeout: float = 60.0,
        show_preview: bool = False,
    ) -> Optional[BarcodeResult]:
        """
        Continuously scan for barcodes until one is found or timeout.

        Args:
            camera: Camera object with capture() method
            timeout: Maximum seconds to scan
            show_preview: Show OpenCV preview window

        Returns:
            BarcodeResult if found, None if timeout
        """
        start_time = datetime.now()

        if show_preview:
            cv2.namedWindow('Barcode Scanner')

        try:
            while True:
                # Check timeout
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    return None

                # Capture frame
                frame = camera.capture()

                # Scan for barcode
                result = self.scan_frame(frame)

                if show_preview:
                    display = self._draw_scan_overlay(frame, result)
                    cv2.imshow('Barcode Scanner', display)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        return None

                if result:
                    return result

        finally:
            if show_preview:
                cv2.destroyWindow('Barcode Scanner')

    def _draw_scan_overlay(
        self,
        frame: np.ndarray,
        result: Optional[BarcodeResult]
    ) -> np.ndarray:
        """Draw scanning overlay on frame."""
        output = frame.copy()
        h, w = output.shape[:2]

        # Draw scan region indicator
        margin = 50
        cv2.rectangle(
            output,
            (margin, margin),
            (w - margin, h - margin),
            (0, 255, 0), 2
        )

        # Draw "Scan barcode" text
        cv2.putText(
            output, "Scan barcode",
            (margin + 10, margin + 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
        )

        # If barcode detected, highlight it
        if result:
            x, y, bw, bh = result.bounding_box
            cv2.rectangle(
                output, (x, y), (x + bw, y + bh),
                (0, 255, 255), 3
            )
            cv2.putText(
                output, result.barcode,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
            )

        return output

    def clear_debounce(self, barcode: Optional[str] = None) -> None:
        """
        Clear debounce history.

        Args:
            barcode: Specific barcode to clear, or None to clear all
        """
        if barcode:
            self._last_detections.pop(barcode, None)
        else:
            self._last_detections.clear()


class LabelScanner:
    """
    Scan wine labels for AI extraction.

    Captures high-quality images of front and back labels
    for sending to Claude Vision API.
    """

    def __init__(self, quality: int = 95):
        """
        Initialize label scanner.

        Args:
            quality: JPEG quality for captured images (0-100)
        """
        self.quality = quality

    def capture_label(
        self,
        camera,
        prompt: str = "Position label in frame",
        show_preview: bool = True,
    ) -> Optional[bytes]:
        """
        Capture a label image.

        Args:
            camera: Camera object with capture() method
            prompt: Text to display to user
            show_preview: Show preview window

        Returns:
            JPEG image bytes, or None if cancelled
        """
        if show_preview:
            cv2.namedWindow('Label Scanner')

        try:
            while True:
                frame = camera.capture()

                if show_preview:
                    display = self._draw_label_overlay(frame, prompt)
                    cv2.imshow('Label Scanner', display)

                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        return None
                    elif key == ord(' ') or key == 13:  # Space or Enter
                        # Capture and encode
                        _, jpeg = cv2.imencode(
                            '.jpg', frame,
                            [cv2.IMWRITE_JPEG_QUALITY, self.quality]
                        )
                        return jpeg.tobytes()
        finally:
            if show_preview:
                cv2.destroyWindow('Label Scanner')

    def _draw_label_overlay(
        self,
        frame: np.ndarray,
        prompt: str
    ) -> np.ndarray:
        """Draw label capture overlay."""
        output = frame.copy()
        h, w = output.shape[:2]

        # Draw center guide rectangle
        margin_x = w // 6
        margin_y = h // 6
        cv2.rectangle(
            output,
            (margin_x, margin_y),
            (w - margin_x, h - margin_y),
            (255, 255, 0), 2
        )

        # Draw prompt
        cv2.putText(
            output, prompt,
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2
        )

        # Draw instructions
        cv2.putText(
            output, "Press SPACE to capture, Q to cancel",
            (20, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1
        )

        return output

    def capture_front_and_back(
        self,
        camera,
        show_preview: bool = True,
    ) -> Optional[Tuple[bytes, bytes]]:
        """
        Capture both front and back label images.

        Args:
            camera: Camera object
            show_preview: Show preview window

        Returns:
            Tuple of (front_jpeg, back_jpeg), or None if cancelled
        """
        # Capture front
        print("Capture FRONT label")
        front = self.capture_label(
            camera,
            prompt="Position FRONT label - Press SPACE",
            show_preview=show_preview,
        )
        if front is None:
            return None

        # Capture back
        print("Capture BACK label")
        back = self.capture_label(
            camera,
            prompt="Position BACK label - Press SPACE",
            show_preview=show_preview,
        )
        if back is None:
            return None

        return (front, back)
