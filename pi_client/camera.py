"""
Camera service for Raspberry Pi.

Provides unified interface to Pi Camera for:
- Barcode scanning
- Label capture
- Rack imaging

Supports both libcamera (Pi OS Bullseye+) and legacy picamera.
"""

import cv2
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass
import time


@dataclass
class CameraConfig:
    """Camera configuration."""
    resolution: Tuple[int, int] = (1920, 1080)
    framerate: int = 30
    rotation: int = 0  # 0, 90, 180, 270
    flip_horizontal: bool = False
    flip_vertical: bool = False
    warmup_seconds: float = 2.0


class PiCamera:
    """
    Raspberry Pi camera interface.

    Automatically selects the best available camera backend:
    1. Picamera2 (recommended for Pi OS Bullseye+)
    2. OpenCV VideoCapture (fallback)
    """

    def __init__(self, config: Optional[CameraConfig] = None):
        """
        Initialize camera.

        Args:
            config: Camera configuration, or None for defaults
        """
        self.config = config or CameraConfig()
        self._camera = None
        self._backend = None

        self._init_camera()

    def _init_camera(self) -> None:
        """Initialize camera with best available backend."""
        # Try Picamera2 first (modern Pi OS)
        try:
            from picamera2 import Picamera2

            self._camera = Picamera2()
            camera_config = self._camera.create_still_configuration(
                main={"size": self.config.resolution}
            )
            self._camera.configure(camera_config)
            self._camera.start()
            self._backend = 'picamera2'

            # Warmup
            time.sleep(self.config.warmup_seconds)
            return

        except ImportError:
            pass
        except Exception as e:
            print(f"Picamera2 failed: {e}")

        # Fallback to OpenCV VideoCapture
        try:
            self._camera = cv2.VideoCapture(0)
            if not self._camera.isOpened():
                raise RuntimeError("Failed to open camera")

            # Set resolution
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.resolution[0])
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.resolution[1])
            self._camera.set(cv2.CAP_PROP_FPS, self.config.framerate)

            self._backend = 'opencv'

            # Warmup
            time.sleep(self.config.warmup_seconds)
            return

        except Exception as e:
            print(f"OpenCV camera failed: {e}")

        raise RuntimeError("No camera backend available")

    def capture(self) -> np.ndarray:
        """
        Capture a single frame.

        Returns:
            BGR image as numpy array
        """
        if self._backend == 'picamera2':
            frame = self._camera.capture_array()
            # Picamera2 returns RGB, convert to BGR for OpenCV
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        else:
            ret, frame = self._camera.read()
            if not ret:
                raise RuntimeError("Failed to capture frame")

        # Apply transformations
        frame = self._apply_transforms(frame)

        return frame

    def _apply_transforms(self, frame: np.ndarray) -> np.ndarray:
        """Apply rotation and flip transforms."""
        # Rotation
        if self.config.rotation == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.config.rotation == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif self.config.rotation == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # Flips
        if self.config.flip_horizontal:
            frame = cv2.flip(frame, 1)
        if self.config.flip_vertical:
            frame = cv2.flip(frame, 0)

        return frame

    def capture_jpeg(self, quality: int = 90) -> bytes:
        """
        Capture frame and encode as JPEG.

        Args:
            quality: JPEG quality (0-100)

        Returns:
            JPEG bytes
        """
        frame = self.capture()
        _, jpeg = cv2.imencode(
            '.jpg', frame,
            [cv2.IMWRITE_JPEG_QUALITY, quality]
        )
        return jpeg.tobytes()

    def start_preview(self, window_name: str = 'Camera Preview') -> None:
        """Start live preview window."""
        cv2.namedWindow(window_name)
        while True:
            frame = self.capture()
            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cv2.destroyWindow(window_name)

    def close(self) -> None:
        """Release camera resources."""
        if self._camera is not None:
            if self._backend == 'picamera2':
                self._camera.stop()
                self._camera.close()
            else:
                self._camera.release()
            self._camera = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class DualModeCamera:
    """
    Camera that supports both rack viewing and close-up scanning.

    For single camera setup where the same camera is used for:
    - Wide view of entire rack (for position detection)
    - Close-up scanning of barcodes/labels

    The user holds the bottle up to the camera for scanning.
    """

    def __init__(self, config: Optional[CameraConfig] = None):
        """
        Initialize dual-mode camera.

        Args:
            config: Camera configuration
        """
        self.camera = PiCamera(config)
        self._mode = 'rack'  # 'rack' or 'scan'

    @property
    def mode(self) -> str:
        """Current camera mode."""
        return self._mode

    def set_rack_mode(self) -> None:
        """Switch to rack viewing mode."""
        self._mode = 'rack'
        # Could adjust focus/exposure here if camera supports it

    def set_scan_mode(self) -> None:
        """Switch to barcode/label scanning mode."""
        self._mode = 'scan'
        # Could adjust focus for close-up here

    def capture(self) -> np.ndarray:
        """Capture frame in current mode."""
        return self.camera.capture()

    def capture_jpeg(self, quality: int = 90) -> bytes:
        """Capture JPEG in current mode."""
        return self.camera.capture_jpeg(quality)

    def close(self) -> None:
        """Release camera resources."""
        self.camera.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience function for testing
def test_camera():
    """Test camera capture and display."""
    print("Testing camera...")

    with PiCamera() as camera:
        print(f"Backend: {camera._backend}")
        print(f"Resolution: {camera.config.resolution}")

        # Capture single frame
        frame = camera.capture()
        print(f"Frame shape: {frame.shape}")

        # Show preview
        print("Press 'q' to quit preview")
        camera.start_preview()


if __name__ == '__main__':
    test_camera()
