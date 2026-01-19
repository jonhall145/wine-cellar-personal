"""
Main workflow controller for wine cellar Pi client.

Orchestrates all components to provide complete workflows for:
- Scanning barcodes
- Syncing with server
"""

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple

from .api_client import APIClient, ServerConfig, Wine
from .camera import CameraConfig, DualModeCamera
from .display import DisplayState, get_display
from .offline_queue import OfflineQueue, SyncManager


class WorkflowState(Enum):
    """Workflow states."""

    IDLE = "idle"
    SCANNING_BARCODE = "scanning_barcode"
    PROCESSING = "processing"
    ERROR = "error"


@dataclass
class WorkflowConfig:
    """Workflow configuration."""

    # Server
    server_host: str = "localhost"
    server_port: int = 8000
    server_https: bool = True
    api_token: str = ""

    # Rack
    rack_id: int = 1

    # Camera
    camera_resolution: Tuple[int, int] = (1920, 1080)
    camera_rotation: int = 0

    # Timeouts
    scan_timeout: float = 60.0

    # Paths
    queue_db_path: str = "~/.wine_cellar/offline_queue.db"


class WorkflowController:
    """
    Main workflow controller.

    Coordinates camera, display, API client, and offline queue.
    """

    def __init__(self, config: Optional[WorkflowConfig] = None):
        """
        Initialize workflow controller.

        Args:
            config: Workflow configuration
        """
        self.config = config or WorkflowConfig()
        self.state = WorkflowState.IDLE

        # Initialize components
        self._init_components()

        # State tracking
        self._current_wine: Optional[Wine] = None
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None

    def _init_components(self) -> None:
        """Initialize all components."""
        # Camera
        camera_config = CameraConfig(
            resolution=self.config.camera_resolution,
            rotation=self.config.camera_rotation,
        )
        self.camera = DualModeCamera(camera_config)

        # Display
        self.display = get_display()

        # API client
        server_config = ServerConfig(
            host=self.config.server_host,
            port=self.config.server_port,
            use_https=self.config.server_https,
            token=self.config.api_token,
        )
        self.api = APIClient(server_config)

        # Offline queue
        self.queue = OfflineQueue(self.config.queue_db_path)

        # Sync manager
        self.sync_manager = SyncManager(self.queue, self.api)
        self.sync_manager.set_callbacks(
            on_sync_complete=self._on_sync_complete,
            on_sync_error=self._on_sync_error,
        )

    def start(self) -> None:
        """Start workflow controller and background tasks."""
        self._running = True

        # Start sync manager
        self.sync_manager.start()

        # Show ready state
        self.display.show_status(DisplayState.IDLE)

    def stop(self) -> None:
        """Stop workflow controller."""
        self._running = False

        # Stop sync manager
        self.sync_manager.stop()

        # Clean up
        self.camera.close()
        self.display.close()

    def _on_sync_complete(self, count: int) -> None:
        """Callback when sync completes."""
        self.display.show_sync_status(pending=0, synced=count)
        time.sleep(2)
        self.display.show_status(DisplayState.IDLE)

    def _on_sync_error(self, error: str) -> None:
        """Callback when sync fails."""
        pending = self.queue.count_pending()
        self.display.show_sync_status(pending=pending)

    def is_online(self) -> bool:
        """Check if server is reachable."""
        return self.api.is_online()

    def get_queue_status(self) -> Dict[str, int]:
        """Get offline queue status."""
        return {
            "pending": self.queue.count_pending(),
        }

    def force_sync(self) -> int:
        """Force immediate sync of queued operations."""
        return self.sync_manager.sync_now()


# Main entry point for running as standalone
def main():
    """Main entry point for Pi client."""
    import argparse

    parser = argparse.ArgumentParser(description="Wine Cellar Pi Client")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--token", default="", help="API token")
    parser.add_argument("--rack-id", type=int, default=1, help="Rack ID")

    args = parser.parse_args()

    config = WorkflowConfig(
        server_host=args.host,
        server_port=args.port,
        api_token=args.token,
        rack_id=args.rack_id,
    )

    controller = WorkflowController(config)

    try:
        controller.start()
        print("Wine Cellar Pi Client started (Vision Disabled)")
        print("Press Ctrl+C to exit")

        # Simple interactive loop
        while True:
            print("\nOptions:")
            print("1. Force sync")
            print("2. Exit")

            choice = input("Choice: ").strip()

            if choice == "1":
                synced = controller.force_sync()
                print(f"Synced {synced} operations")
            elif choice == "2":
                break

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
