"""
Main workflow controller for wine cellar Pi client.

Orchestrates all components to provide complete workflows for:
- Adding bottles (scan barcode → lookup/create → detect position)
- Removing bottles (scan label → detect empty position)
- Hourly rack snapshots
- Daily reconciliation
"""

import time
import threading
import schedule
from typing import Optional, Tuple, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum

from .camera import PiCamera, DualModeCamera, CameraConfig
from .display import DisplayManager, DisplayState, get_display
from .api_client import APIClient, Wine, ServerConfig, ConnectionError
from .offline_queue import (
    OfflineQueue, SyncManager,
    queue_add_wine, queue_remove_wine, queue_position_change, queue_rack_snapshot
)
from .rack_vision import AutoDetectingCalibrator, GridDetector, BottleDetector


class WorkflowState(Enum):
    """Workflow states."""
    IDLE = "idle"
    SCANNING_BARCODE = "scanning_barcode"
    CAPTURING_LABEL = "capturing_label"
    DETECTING_POSITION = "detecting_position"
    CONFIRMING = "confirming"
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
    rack_rows: int = 5
    rack_cols: int = 10

    # Camera
    camera_resolution: Tuple[int, int] = (1920, 1080)
    camera_rotation: int = 0

    # Timeouts
    scan_timeout: float = 60.0
    position_detect_timeout: float = 30.0

    # Scheduling
    snapshot_interval_hours: int = 1
    reconciliation_hour: int = 3  # 3 AM

    # Paths
    queue_db_path: str = "~/.wine_cellar/offline_queue.db"


class WorkflowController:
    """
    Main workflow controller.

    Coordinates camera, display, API client, offline queue,
    and vision system to provide complete add/remove workflows.
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
        self._before_image: Optional[any] = None
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

        # Vision components
        self.calibrator = AutoDetectingCalibrator(
            rows=self.config.rack_rows,
            cols=self.config.rack_cols,
        )
        self.grid_detector = GridDetector(self.calibrator)
        self.bottle_detector = BottleDetector()

    def start(self) -> None:
        """Start workflow controller and background tasks."""
        self._running = True

        # Start sync manager
        self.sync_manager.start()

        # Start scheduler thread
        self._setup_schedule()
        self._scheduler_thread = threading.Thread(
            target=self._run_scheduler,
            daemon=True
        )
        self._scheduler_thread.start()

        # Show ready state
        self.display.show_status(DisplayState.IDLE)

    def stop(self) -> None:
        """Stop workflow controller."""
        self._running = False

        # Stop sync manager
        self.sync_manager.stop()

        # Stop scheduler
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5.0)

        # Clean up
        self.camera.close()
        self.display.close()

    def _setup_schedule(self) -> None:
        """Set up scheduled tasks."""
        # Hourly rack snapshots
        schedule.every(self.config.snapshot_interval_hours).hours.do(
            self._take_rack_snapshot
        )

        # Daily reconciliation at configured hour
        schedule.every().day.at(f"{self.config.reconciliation_hour:02d}:00").do(
            self._run_reconciliation
        )

    def _run_scheduler(self) -> None:
        """Run scheduler loop."""
        while self._running:
            schedule.run_pending()
            time.sleep(1)

    # ==================== Add Bottle Workflow ====================

    def add_bottle_workflow(self) -> bool:
        """
        Complete workflow for adding a bottle to the cellar.

        1. Scan barcode
        2. Look up or create wine
        3. Detect rack position
        4. Record in database

        Returns:
            True if bottle was added successfully
        """
        try:
            # Step 1: Scan barcode
            self.state = WorkflowState.SCANNING_BARCODE
            self.display.show_status(DisplayState.SCANNING)

            self.camera.set_scan_mode()
            barcode_result = self.bottle_detector.scan_continuous(
                self.camera.camera,
                timeout=self.config.scan_timeout
            )

            if not barcode_result:
                self.display.show_error("No barcode found")
                self.state = WorkflowState.IDLE
                return False

            barcode = barcode_result.data
            self.display.show_barcode_found(barcode)

            # Step 2: Look up wine
            wine = self._lookup_or_create_wine(barcode)
            if not wine:
                self.state = WorkflowState.ERROR
                return False

            self._current_wine = wine

            # Step 3: Capture "before" rack image
            self.display.show_message("Place bottle", "in rack...")
            time.sleep(2)  # Give user time to read

            self.camera.set_rack_mode()
            self._before_image = self.camera.capture()
            before_state = self.grid_detector.analyze_grid(self._before_image)

            # Wait for user to place bottle
            self.display.show_message("Waiting...", "Place bottle now")
            time.sleep(5)  # Configurable delay

            # Step 4: Capture "after" and detect position
            self.state = WorkflowState.DETECTING_POSITION
            position = self._detect_added_position(before_state)

            if position:
                row, col = position
                self.display.show_position_detected(row, col)

                # Step 5: Record in database
                success = self._record_bottle_added(wine, row, col)
                if success:
                    self.display.show_wine_added(
                        wine.name,
                        f"R{row+1}C{col+1}"
                    )
                    self.state = WorkflowState.IDLE
                    return True
            else:
                # Position not auto-detected - queue for review
                self.display.show_message("Position unclear", "Check web UI")
                self._queue_for_review(wine, "added")

            self.state = WorkflowState.IDLE
            return False

        except Exception as e:
            self.display.show_error(str(e)[:32])
            self.state = WorkflowState.ERROR
            return False

    def _lookup_or_create_wine(self, barcode: str) -> Optional[Wine]:
        """Look up wine by barcode or create from label capture."""
        try:
            # Try online lookup first
            if self.api.is_online():
                wine = self.api.get_wine_by_barcode(barcode)
                if wine:
                    return wine
        except ConnectionError:
            self.display.show_status(DisplayState.OFFLINE)

        # Wine not found - capture labels for AI extraction
        self.state = WorkflowState.CAPTURING_LABEL
        self.display.show_unknown_wine()

        self.camera.set_scan_mode()
        labels = self.bottle_detector.label_scanner.capture_front_and_back(
            self.camera.camera
        )

        if labels:
            front_image, back_image = labels
            try:
                if self.api.is_online():
                    wine = self.api.create_wine_from_labels(
                        front_image, back_image, barcode
                    )
                    return wine
            except ConnectionError:
                # Queue for later
                self.display.show_status(DisplayState.OFFLINE)

        # Create minimal wine entry
        return Wine(barcode=barcode, name=f"Unknown ({barcode})")

    def _detect_added_position(
        self,
        before_state: 'GridState'
    ) -> Optional[Tuple[int, int]]:
        """Detect which position a bottle was added to."""
        after_image = self.camera.capture()
        after_state = self.grid_detector.analyze_grid(after_image)

        position = self.grid_detector.detect_single_change(
            before_state,
            after_state,
            expected_type='added'
        )

        return position

    def _record_bottle_added(
        self,
        wine: Wine,
        row: int,
        col: int
    ) -> bool:
        """Record bottle addition to database."""
        try:
            if self.api.is_online():
                self.api.add_wine_to_position(
                    wine.id,
                    self.config.rack_id,
                    row,
                    col
                )
                return True
        except ConnectionError:
            pass

        # Queue offline
        queue_add_wine(
            self.queue,
            wine.id or 0,
            self.config.rack_id,
            row,
            col
        )
        self.display.show_status(DisplayState.OFFLINE)
        return True

    # ==================== Remove Bottle Workflow ====================

    def remove_bottle_workflow(self) -> bool:
        """
        Complete workflow for removing a bottle from the cellar.

        1. Capture rack "before" image
        2. Wait for user to remove bottle
        3. Detect which position is now empty
        4. Optionally scan bottle to confirm
        5. Record removal

        Returns:
            True if bottle was removed successfully
        """
        try:
            # Step 1: Capture "before" image
            self.camera.set_rack_mode()
            self.display.show_message("Scanning rack", "Please wait...")

            before_image = self.camera.capture()
            before_state = self.grid_detector.analyze_grid(before_image)

            # Step 2: Wait for removal
            self.display.show_message("Remove bottle", "from rack...")
            time.sleep(5)

            # Step 3: Detect empty position
            self.state = WorkflowState.DETECTING_POSITION
            after_image = self.camera.capture()
            after_state = self.grid_detector.analyze_grid(after_image)

            position = self.grid_detector.detect_single_change(
                before_state,
                after_state,
                expected_type='removed'
            )

            if position:
                row, col = position
                self.display.show_position_detected(row, col)

                # Get wine info from position
                wine = self._get_wine_at_position(row, col)

                # Record removal
                success = self._record_bottle_removed(row, col)
                if success:
                    wine_name = wine.name if wine else "Bottle"
                    self.display.show_wine_removed(wine_name, f"R{row+1}C{col+1}")
                    self.state = WorkflowState.IDLE
                    return True
            else:
                self.display.show_message("Position unclear", "Check web UI")
                self._queue_for_review(None, "removed", after_image)

            self.state = WorkflowState.IDLE
            return False

        except Exception as e:
            self.display.show_error(str(e)[:32])
            self.state = WorkflowState.ERROR
            return False

    def _get_wine_at_position(self, row: int, col: int) -> Optional[Wine]:
        """Get wine at position from server."""
        try:
            if self.api.is_online():
                position = self.api.get_position(
                    self.config.rack_id, row, col
                )
                if position:
                    return position.wine
        except ConnectionError:
            pass
        return None

    def _record_bottle_removed(self, row: int, col: int) -> bool:
        """Record bottle removal from database."""
        try:
            if self.api.is_online():
                self.api.remove_wine_from_position(
                    self.config.rack_id, row, col
                )
                return True
        except ConnectionError:
            pass

        # Queue offline
        queue_remove_wine(self.queue, self.config.rack_id, row, col)
        self.display.show_status(DisplayState.OFFLINE)
        return True

    # ==================== Scheduled Tasks ====================

    def _take_rack_snapshot(self) -> None:
        """Take and upload hourly rack snapshot."""
        try:
            self.camera.set_rack_mode()
            image = self.camera.capture_jpeg()
            grid_state = self.grid_detector.analyze_grid(
                self.camera.capture()
            )

            state_dict = {
                "rows": grid_state.rows,
                "cols": grid_state.cols,
                "occupied": grid_state.occupied,
            }

            try:
                if self.api.is_online():
                    self.api.upload_rack_snapshot(
                        self.config.rack_id,
                        image,
                        state_dict
                    )
                    return
            except ConnectionError:
                pass

            # Queue offline
            queue_rack_snapshot(
                self.queue,
                self.config.rack_id,
                image,
                state_dict
            )

        except Exception as e:
            print(f"Snapshot error: {e}")

    def _run_reconciliation(self) -> None:
        """Run daily reconciliation check."""
        try:
            self.camera.set_rack_mode()
            image = self.camera.capture()
            grid_state = self.grid_detector.analyze_grid(image)

            # Compare with server state
            if not self.api.is_online():
                return

            server_positions = self.api.get_rack_positions(self.config.rack_id)

            discrepancies = []
            for pos in server_positions:
                row, col = pos.row, pos.col
                camera_occupied = grid_state.occupied[row][col]
                server_occupied = not pos.is_empty

                if camera_occupied != server_occupied:
                    discrepancies.append({
                        "row": row,
                        "col": col,
                        "camera_says": "occupied" if camera_occupied else "empty",
                        "server_says": "occupied" if server_occupied else "empty",
                    })

            if discrepancies:
                # Report to server for review
                self.api.report_position_change(
                    rack_id=self.config.rack_id,
                    row=0, col=0,  # Multiple positions
                    change_type="reconciliation",
                    confidence=grid_state.confidence,
                    image=self.camera.capture_jpeg(),
                )

        except Exception as e:
            print(f"Reconciliation error: {e}")

    # ==================== Helper Methods ====================

    def _queue_for_review(
        self,
        wine: Optional[Wine],
        change_type: str,
        image: Optional[any] = None
    ) -> None:
        """Queue unclear change for web UI review."""
        image_bytes = None
        if image is not None:
            import cv2
            _, jpeg = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_bytes = jpeg.tobytes()

        queue_position_change(
            self.queue,
            self.config.rack_id,
            row=-1,  # Unknown
            col=-1,
            change_type=change_type,
            wine_id=wine.id if wine and wine.id else None,
            confidence=0.0,
            image=image_bytes,
        )

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
    parser.add_argument("--rows", type=int, default=5, help="Rack rows")
    parser.add_argument("--cols", type=int, default=10, help="Rack columns")

    args = parser.parse_args()

    config = WorkflowConfig(
        server_host=args.host,
        server_port=args.port,
        api_token=args.token,
        rack_id=args.rack_id,
        rack_rows=args.rows,
        rack_cols=args.cols,
    )

    controller = WorkflowController(config)

    try:
        controller.start()
        print("Wine Cellar Pi Client started")
        print("Press Ctrl+C to exit")

        # Simple interactive loop
        while True:
            print("\nOptions:")
            print("1. Add bottle")
            print("2. Remove bottle")
            print("3. Take snapshot")
            print("4. Force sync")
            print("5. Exit")

            choice = input("Choice: ").strip()

            if choice == "1":
                controller.add_bottle_workflow()
            elif choice == "2":
                controller.remove_bottle_workflow()
            elif choice == "3":
                controller._take_rack_snapshot()
                print("Snapshot taken")
            elif choice == "4":
                synced = controller.force_sync()
                print(f"Synced {synced} operations")
            elif choice == "5":
                break

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
