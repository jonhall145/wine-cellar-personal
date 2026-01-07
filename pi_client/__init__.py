"""
Wine Cellar Raspberry Pi Client.

This package provides the Pi-side components for:
- Camera-based barcode scanning
- Wine label capture for AI extraction
- Rack position detection via computer vision
- LCD display management
- Offline queue for server sync

Main components:
- camera: Pi Camera interface
- rack_vision: Grid detection and calibration
- display: LCD display manager (see plan for implementation)
- workflow: Main workflow controller (see plan for implementation)
- api_client: Server API client (see plan for implementation)
- offline_queue: Offline operation queue (see plan for implementation)
"""

__version__ = '0.1.0'
