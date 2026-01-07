"""
Wine Cellar Raspberry Pi Client.

This package provides the Pi-side components for:
- Camera-based barcode scanning
- Wine label capture for AI extraction
- Rack position detection via computer vision
- LCD display management
- Offline queue for server sync

Main components:
- camera: Pi Camera interface (PiCamera, DualModeCamera)
- rack_vision: Grid detection and calibration
- display: LCD display manager (DisplayManager)
- workflow: Main workflow controller (WorkflowController)
- api_client: Server API client (APIClient)
- offline_queue: Offline operation queue (OfflineQueue, SyncManager)

Usage:
    from pi_client import WorkflowController, WorkflowConfig

    config = WorkflowConfig(
        server_host="192.168.1.100",
        server_port=8000,
        rack_rows=5,
        rack_cols=10,
    )
    controller = WorkflowController(config)
    controller.start()

    # Run workflows
    controller.add_bottle_workflow()
    controller.remove_bottle_workflow()

    controller.stop()
"""

__version__ = '0.1.0'

from .camera import PiCamera, DualModeCamera, CameraConfig
from .display import DisplayManager, DisplayState, get_display
from .api_client import APIClient, ServerConfig, Wine, StoragePosition
from .offline_queue import OfflineQueue, SyncManager, QueuedOperation
from .workflow import WorkflowController, WorkflowConfig, WorkflowState

__all__ = [
    # Camera
    'PiCamera',
    'DualModeCamera',
    'CameraConfig',
    # Display
    'DisplayManager',
    'DisplayState',
    'get_display',
    # API Client
    'APIClient',
    'ServerConfig',
    'Wine',
    'StoragePosition',
    # Offline Queue
    'OfflineQueue',
    'SyncManager',
    'QueuedOperation',
    # Workflow
    'WorkflowController',
    'WorkflowConfig',
    'WorkflowState',
]
