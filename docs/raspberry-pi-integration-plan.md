# Wine Cellar Raspberry Pi Integration Plan

## Overview

This document outlines the phased implementation plan for:
1. Maintaining web/browser access and management
2. Migrating to a Raspberry Pi with local WiFi access
3. Hardware integration (1-line display, fixed camera)
4. Automated bottle tracking workflows (add/remove/reconcile)

---

## Phase 1: Web Access Hardening & HTTPS Fixes

**Goal**: Ensure robust web access that will continue to work alongside Pi deployment.

### 1.1 HTTPS Improvements

**Current State**:
- `run_https.sh` uses self-signed certificates
- Mobile browsers require HTTPS for camera access
- Self-signed certs cause browser warnings

**Proposed Solutions**:

| Option | Pros | Cons |
|--------|------|------|
| Let's Encrypt (certbot) | Free, trusted certs | Requires public domain |
| mkcert local CA | No warnings on your devices | Requires CA install on each device |
| Cloudflare Tunnel | No port forwarding needed | Requires Cloudflare account |

**Recommendation**: Use **mkcert** for local development and Pi deployment:
```bash
# Install mkcert and create local CA
mkcert -install
mkcert localhost 192.168.x.x wine-cellar.local
```

**Tasks**:
- [ ] Create mkcert setup script (`scripts/setup-local-ca.sh`)
- [ ] Update `run_https.sh` to use mkcert certs if available
- [ ] Add documentation for CA installation on mobile devices
- [ ] Consider Cloudflare Tunnel for remote access option

### 1.2 Network Configuration for Pi Access

**Tasks**:
- [ ] Document static IP configuration for Pi
- [ ] Create mDNS/Avahi setup for `wine-cellar.local` discovery
- [ ] Configure Django `ALLOWED_HOSTS` for local network patterns
- [ ] Add CORS configuration for API access from different origins

---

## Phase 2: API Layer for Hardware Integration

**Goal**: Create dedicated API endpoints for hardware devices (Pi, scanners, cameras).

### 2.1 New API Endpoints

```
POST /api/v1/hardware/barcode-lookup/
  Request:  { "barcode": "1234567890123" }
  Response: { "found": true, "wine": {...}, "action": "add_bottle" }
            { "found": false, "action": "request_labels" }

POST /api/v1/hardware/label-extract/
  Request:  { "images": [base64_front, base64_back] }
  Response: { "extracted_data": {...}, "confidence": "high" }

POST /api/v1/hardware/bottle-add/
  Request:  {
    "wine_id": 123,           # or null for new wine
    "wine_data": {...},       # if creating new
    "storage_id": 1,
    "row": 3, "column": 2,
    "detected_position": true  # from vision system
  }
  Response: { "success": true, "storage_item_id": 456 }

POST /api/v1/hardware/bottle-remove/
  Request:  {
    "wine_id": 123,           # or null if unknown
    "barcode": "...",         # if scanned
    "position": {"row": 3, "column": 2}  # from vision diff
  }
  Response: { "success": true, "removed_item": {...} }

GET /api/v1/hardware/rack-state/
  Response: {
    "storage_id": 1,
    "grid": [[null, wine_id, wine_id], [wine_id, null, null], ...],
    "last_image_capture": "2026-01-07T10:00:00Z"
  }

POST /api/v1/hardware/rack-image/
  Request:  { "storage_id": 1, "image": base64, "capture_type": "scheduled|manual" }
  Response: { "success": true, "analysis_task_id": "abc123" }

GET /api/v1/hardware/reconciliation-status/
  Response: {
    "last_check": "...",
    "issues": [...],
    "drift_detected": true
  }
```

### 2.2 Authentication for Hardware

**Options**:
- API keys per device (simple, stateless)
- JWT tokens with device registration
- mTLS with client certificates (most secure)

**Recommendation**: Start with API keys, migrate to JWT later:
```python
# New model
class HardwareDevice(models.Model):
    name = models.CharField(max_length=100)  # "Kitchen Pi Scanner"
    device_type = models.CharField(choices=['pi', 'scanner', 'camera'])
    api_key = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    last_seen = models.DateTimeField(null=True)
    is_active = models.BooleanField(default=True)
```

**Tasks**:
- [ ] Create HardwareDevice model with API key auth
- [ ] Add `@hardware_api_auth` decorator for endpoints
- [ ] Create device management UI in settings
- [ ] Add rate limiting for hardware endpoints

---

## Phase 3: Rack Vision System (Non-AI Hardware Analysis)

**Goal**: Use computer vision (non-AI) to detect bottle positions in rack.

### 3.1 Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Pi Camera      │────▶│  OpenCV on Pi    │────▶│  Django API     │
│  (Fixed mount)  │     │  (Local process) │     │  (Position DB)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌──────────────────┐
                        │  Position Diff   │
                        │  Detection       │
                        └──────────────────┘
```

### 3.2 OpenCV Processing Pipeline

```python
# rack_vision/detector.py (runs on Pi)

import cv2
import numpy as np

class RackDetector:
    def __init__(self, config):
        self.rows = config['rows']
        self.cols = config['columns']
        self.calibration = config['calibration']  # Corner points

    def detect_grid(self, image):
        """Detect rack grid and return cell states."""
        # 1. Apply perspective transform to get flat view
        warped = self.apply_perspective(image)

        # 2. Convert to grayscale
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

        # 3. Divide into grid cells based on calibration
        cells = self.divide_into_cells(gray)

        # 4. For each cell, determine if bottle present
        states = []
        for row in cells:
            row_states = []
            for cell in row:
                occupied = self.is_cell_occupied(cell)
                row_states.append(occupied)
            states.append(row_states)

        return states

    def is_cell_occupied(self, cell_image):
        """Determine if a cell contains a bottle."""
        # Simple approach: check for circular shapes (bottle bottoms)
        # or significant color/texture difference from empty

        # Edge detection
        edges = cv2.Canny(cell_image, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size

        # Threshold for "something present"
        return edge_density > 0.1

    def diff_states(self, before, after):
        """Find which positions changed."""
        added = []
        removed = []

        for r in range(len(before)):
            for c in range(len(before[r])):
                if not before[r][c] and after[r][c]:
                    added.append((r, c))
                elif before[r][c] and not after[r][c]:
                    removed.append((r, c))

        return {'added': added, 'removed': removed}
```

### 3.3 Calibration System

The camera position relative to the rack must be calibrated:

```python
# rack_vision/calibration.py

class RackCalibrator:
    """Interactive calibration for rack position detection."""

    def __init__(self, storage_id, camera):
        self.storage_id = storage_id
        self.camera = camera
        self.corner_points = []  # [(x,y), ...] for 4 corners

    def capture_calibration_frame(self):
        """Capture frame and prompt user to mark corners."""
        frame = self.camera.capture()
        return frame

    def set_corners(self, corners):
        """Set the 4 corners of the rack in the image."""
        self.corner_points = corners
        self.save_calibration()

    def save_calibration(self):
        """Save calibration to config file."""
        config = {
            'storage_id': self.storage_id,
            'corners': self.corner_points,
            'rows': self.rows,
            'columns': self.cols,
            'calibrated_at': datetime.now().isoformat()
        }
        with open(f'/etc/wine-cellar/calibration_{self.storage_id}.json', 'w') as f:
            json.dump(config, f)
```

### 3.4 Tasks

- [ ] Create `rack_vision/` Python package for Pi
- [ ] Implement `RackDetector` class with OpenCV
- [ ] Create calibration wizard (web UI + Pi display)
- [ ] Add perspective transformation for angled camera views
- [ ] Implement diff detection between captures
- [ ] Add lighting normalization for consistent detection
- [ ] Create test suite with sample rack images

---

## Phase 4: Raspberry Pi Client Application

**Goal**: Create the Pi-side application that orchestrates hardware.

### 4.1 Hardware Setup

**Components**:
- Raspberry Pi 4 (or Pi 5 for better performance)
- Pi Camera Module v2 or v3 (fixed mount)
- 1-line LCD display (16x2 or 20x4 character display)
- USB barcode scanner (or camera-based scanning)
- Optional: Button for manual triggers

### 4.2 Software Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Pi Client Application                  │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │  Barcode    │  │   Camera    │  │    Display      │ │
│  │  Scanner    │  │   Service   │  │    Manager      │ │
│  │  Service    │  │             │  │                 │ │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │
│         │                │                  │          │
│         └────────────────┼──────────────────┘          │
│                          │                             │
│                   ┌──────▼──────┐                      │
│                   │  Workflow   │                      │
│                   │  Controller │                      │
│                   └──────┬──────┘                      │
│                          │                             │
│                   ┌──────▼──────┐                      │
│                   │  API Client │                      │
│                   │  (sync w/   │                      │
│                   │   server)   │                      │
│                   └─────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

### 4.3 Display Manager

```python
# pi_client/display.py

import board
import digitalio
import adafruit_character_lcd.character_lcd as characterlcd

class DisplayManager:
    """Manage 16x2 or 20x4 character LCD display."""

    def __init__(self, cols=16, rows=2):
        # GPIO pin configuration
        lcd_rs = digitalio.DigitalInOut(board.D26)
        lcd_en = digitalio.DigitalInOut(board.D19)
        lcd_d4 = digitalio.DigitalInOut(board.D13)
        lcd_d5 = digitalio.DigitalInOut(board.D6)
        lcd_d6 = digitalio.DigitalInOut(board.D5)
        lcd_d7 = digitalio.DigitalInOut(board.D11)

        self.lcd = characterlcd.Character_LCD_Mono(
            lcd_rs, lcd_en, lcd_d4, lcd_d5, lcd_d6, lcd_d7,
            cols, rows
        )

    def show_message(self, line1, line2=""):
        """Display message on LCD."""
        self.lcd.clear()
        self.lcd.message = f"{line1[:16]}\n{line2[:16]}"

    def show_status(self, status):
        """Show standard status messages."""
        messages = {
            'ready': ("Ready", "Scan barcode"),
            'scanning': ("Scanning...", ""),
            'found': ("Wine found!", "Adding..."),
            'not_found': ("Unknown wine", "Scan labels"),
            'label_front': ("Scan front", "label"),
            'label_back': ("Scan back", "label"),
            'added': ("Bottle added", "to rack"),
            'removed': ("Bottle removed", "from rack"),
            'error': ("Error", "Check logs"),
            'reconciling': ("Checking rack", "Please wait..."),
        }
        line1, line2 = messages.get(status, ("Unknown", "status"))
        self.show_message(line1, line2)
```

### 4.4 Workflow Controller

```python
# pi_client/workflow.py

class WorkflowController:
    """Main workflow orchestration for bottle add/remove."""

    def __init__(self, api_client, camera, scanner, display, rack_detector):
        self.api = api_client
        self.camera = camera
        self.scanner = scanner
        self.display = display
        self.detector = rack_detector
        self.baseline_state = None

    async def handle_barcode_scan(self, barcode):
        """Handle incoming barcode scan."""
        self.display.show_status('scanning')

        # Look up barcode
        result = await self.api.lookup_barcode(barcode)

        if result['found']:
            return await self.add_known_wine(result['wine'])
        else:
            return await self.add_unknown_wine(barcode)

    async def add_known_wine(self, wine):
        """Add a wine that's already in the database."""
        self.display.show_status('found')

        # Capture rack state before
        self.display.show_message("Place bottle", "in rack...")
        before_state = self.capture_rack_state()

        # Wait for user to place bottle (could use button or timeout)
        await self.wait_for_action()

        # Capture rack state after
        after_state = self.capture_rack_state()

        # Diff to find position
        diff = self.detector.diff_states(before_state, after_state)

        if len(diff['added']) == 1:
            row, col = diff['added'][0]
            result = await self.api.add_bottle(
                wine_id=wine['id'],
                row=row,
                column=col,
                detected_position=True
            )
            self.display.show_status('added')
            return result
        elif len(diff['added']) == 0:
            self.display.show_message("No change", "detected")
        else:
            self.display.show_message("Multiple", "changes!")

    async def add_unknown_wine(self, barcode):
        """Add a wine not in database - requires label scans."""
        self.display.show_status('not_found')
        await asyncio.sleep(1)

        # Request front label scan
        self.display.show_status('label_front')
        front_image = await self.capture_label_image()

        # Request back label scan
        self.display.show_status('label_back')
        back_image = await self.capture_label_image()

        # Send to API for extraction
        self.display.show_message("Analyzing", "labels...")
        extracted = await self.api.extract_labels([front_image, back_image])

        # Create wine and add bottle
        wine_data = extracted['wine_data']
        wine_data['barcode'] = barcode

        # Now add to rack (same flow as known wine)
        return await self.add_new_wine_to_rack(wine_data)

    async def handle_bottle_removal(self):
        """Handle bottle removal workflow."""
        # Capture current state (should be from scheduled image)
        before_state = self.baseline_state

        self.display.show_message("Scan removed", "bottle")

        # Wait for barcode scan
        barcode = await self.scanner.wait_for_scan(timeout=60)

        if barcode:
            wine = await self.api.lookup_barcode(barcode)
        else:
            wine = None

        # Capture after state
        after_state = self.capture_rack_state()

        # Diff to find removed position
        diff = self.detector.diff_states(before_state, after_state)

        if len(diff['removed']) == 1:
            row, col = diff['removed'][0]
            result = await self.api.remove_bottle(
                wine_id=wine['id'] if wine else None,
                position={'row': row, 'column': col}
            )
            self.display.show_status('removed')
            return result
        else:
            self.display.show_message("Position", "unclear")
```

### 4.5 Tasks

- [ ] Create `pi_client/` package structure
- [ ] Implement `DisplayManager` for LCD
- [ ] Implement `CameraService` for image capture
- [ ] Implement `BarcodeScanner` service (USB or camera-based)
- [ ] Implement `WorkflowController` for orchestration
- [ ] Create `APIClient` for server communication
- [ ] Add systemd service for auto-start
- [ ] Create installation script for Pi

---

## Phase 5: Scheduled Tasks & Reconciliation

**Goal**: Implement scheduled rack imaging and database reconciliation.

### 5.1 Scheduled Image Capture

```python
# pi_client/scheduler.py

import schedule
import time

class RackScheduler:
    """Schedule periodic rack captures."""

    def __init__(self, camera, api_client, rack_detector):
        self.camera = camera
        self.api = api_client
        self.detector = rack_detector

    def start(self):
        # Capture every hour
        schedule.every().hour.do(self.capture_and_upload)

        # Daily reconciliation at 3 AM
        schedule.every().day.at("03:00").do(self.reconcile)

        while True:
            schedule.run_pending()
            time.sleep(60)

    def capture_and_upload(self):
        """Capture rack image and upload to server."""
        image = self.camera.capture()
        state = self.detector.detect_grid(image)

        self.api.upload_rack_image(
            image=image,
            state=state,
            capture_type='scheduled'
        )
```

### 5.2 Django Reconciliation System

```python
# wine_cellar/apps/storage/models.py (additions)

class RackSnapshot(models.Model):
    """Store periodic rack state snapshots."""
    storage = models.ForeignKey(Storage, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='rack_snapshots/')
    detected_state = models.JSONField()  # [[bool, bool, ...], ...]
    captured_at = models.DateTimeField(auto_now_add=True)
    capture_type = models.CharField(
        choices=[('scheduled', 'Scheduled'), ('manual', 'Manual')],
        default='scheduled'
    )

class ReconciliationIssue(models.Model):
    """Track discrepancies between rack and database."""
    storage = models.ForeignKey(Storage, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    issue_type = models.CharField(choices=[
        ('missing', 'Bottle in DB but not in rack'),
        ('extra', 'Bottle in rack but not in DB'),
        ('mismatch', 'Position mismatch'),
    ])
    row = models.IntegerField()
    column = models.IntegerField()
    expected_wine = models.ForeignKey(Wine, null=True, on_delete=models.SET_NULL)
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True)
    resolution_notes = models.TextField(blank=True)
```

### 5.3 Reconciliation Service

```python
# wine_cellar/apps/storage/services/reconciliation.py

class ReconciliationService:
    """Compare rack images with database state."""

    def reconcile(self, storage_id, detected_state):
        """Compare detected state with database."""
        storage = Storage.objects.get(id=storage_id)

        # Get database state
        db_state = self.get_database_state(storage)

        # Compare
        issues = []

        for row in range(storage.rows):
            for col in range(storage.columns):
                detected = detected_state[row][col]
                db_has = db_state[row][col] is not None

                if detected and not db_has:
                    issues.append({
                        'type': 'extra',
                        'row': row,
                        'column': col,
                        'message': f'Bottle detected at ({row},{col}) but not in database'
                    })
                elif not detected and db_has:
                    issues.append({
                        'type': 'missing',
                        'row': row,
                        'column': col,
                        'wine': db_state[row][col],
                        'message': f'Bottle expected at ({row},{col}) but not detected'
                    })

        # Store issues
        for issue in issues:
            ReconciliationIssue.objects.create(
                storage=storage,
                user=storage.user,
                issue_type=issue['type'],
                row=issue['row'],
                column=issue['column'],
                expected_wine_id=issue.get('wine', {}).get('id')
            )

        return issues

    def get_database_state(self, storage):
        """Build grid from database."""
        items = StorageItem.objects.filter(
            storage=storage,
            deleted=False
        ).select_related('wine')

        grid = [[None] * storage.columns for _ in range(storage.rows)]

        for item in items:
            if item.row is not None and item.column is not None:
                grid[item.row][item.column] = {
                    'id': item.wine.id,
                    'name': item.wine.name,
                    'item_id': item.id
                }

        return grid
```

### 5.4 Web UI for Issues

Add to dashboard:
- Reconciliation status badge (green/yellow/red)
- List of unresolved issues
- Quick actions: Mark resolved, Move bottle, Remove from DB

### 5.5 Tasks

- [ ] Create `RackSnapshot` and `ReconciliationIssue` models
- [ ] Implement `ReconciliationService`
- [ ] Add API endpoint for receiving rack images
- [ ] Create Celery task for async reconciliation
- [ ] Add reconciliation status to homepage dashboard
- [ ] Create issues list view with resolution actions
- [ ] Add email/notification for critical issues

---

## Phase 6: Integration & Testing

### 6.1 End-to-End Testing

- [ ] Test barcode scan → known wine → position detection → add
- [ ] Test barcode scan → unknown wine → label capture → add
- [ ] Test bottle removal workflow
- [ ] Test scheduled capture and upload
- [ ] Test reconciliation with simulated drift

### 6.2 Error Handling

- [ ] Camera unavailable fallback
- [ ] Network outage handling (queue operations)
- [ ] Position detection failure handling
- [ ] API timeout handling

### 6.3 Documentation

- [ ] Pi hardware setup guide
- [ ] Camera mounting and calibration guide
- [ ] Troubleshooting guide
- [ ] API documentation for hardware endpoints

---

## Implementation Priority

### Must Have (Phase 1-2)
1. HTTPS improvements with mkcert
2. Hardware API endpoints
3. API key authentication for devices

### Should Have (Phase 3-4)
4. OpenCV rack detection on Pi
5. Display manager for LCD
6. Barcode scan workflow
7. Label scan workflow with Claude AI

### Nice to Have (Phase 5-6)
8. Scheduled image capture
9. Daily reconciliation
10. Issue management UI

---

## Technical Decisions Needed

1. **Camera mounting**: Fixed position vs adjustable mount?
2. **Lighting**: Add LED strip for consistent lighting?
3. **Multiple racks**: Support multiple cameras/racks?
4. **Offline mode**: Queue operations when server unavailable?
5. **Position confirmation**: Require user to confirm detected position?
6. **Display type**: 16x2 LCD vs small OLED screen?

---

## Estimated Complexity

| Component | Complexity | Dependencies |
|-----------|------------|--------------|
| HTTPS improvements | Low | None |
| Hardware API | Medium | None |
| Rack detection | High | OpenCV, calibration |
| Pi client | High | Camera, display, scanner |
| Reconciliation | Medium | Rack detection |
| Web UI updates | Low | Reconciliation |

---

## Next Steps

1. Review and approve this plan
2. Decide on technical decisions above
3. Order Raspberry Pi hardware
4. Begin Phase 1 (HTTPS) implementation
5. Parallel: Develop rack detection prototype
