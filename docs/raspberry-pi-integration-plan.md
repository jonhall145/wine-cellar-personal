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

### 4.3 Display Manager (Freenove I2C LCD 1602)

The Freenove I2C LCD 1602 uses PCF8574 I2C expander (typically address 0x27 or 0x3F).

```python
# pi_client/display.py

from RPLCD.i2c import CharLCD
import time

class DisplayManager:
    """Manage Freenove I2C LCD 1602 display."""

    def __init__(self, i2c_address=0x27):
        """
        Initialize LCD display.

        Args:
            i2c_address: I2C address (0x27 or 0x3F for PCF8574)
                         Run `i2cdetect -y 1` to find actual address
        """
        self.lcd = CharLCD(
            i2c_expander='PCF8574',
            address=i2c_address,
            port=1,  # /dev/i2c-1 on Pi
            cols=16,
            rows=2,
            dotsize=8,
            charmap='A02',
            auto_linebreaks=True
        )
        self.lcd.clear()

    def show_message(self, line1, line2=""):
        """Display message on LCD."""
        self.lcd.clear()
        # Pad/truncate to 16 chars
        line1 = line1[:16].ljust(16)
        line2 = line2[:16].ljust(16)
        self.lcd.write_string(line1)
        self.lcd.cursor_pos = (1, 0)
        self.lcd.write_string(line2)

    def show_status(self, status):
        """Show standard status messages."""
        messages = {
            'ready': ("Ready", "Scan barcode"),
            'scanning': ("Scanning...", ""),
            'found': ("Wine found!", "Place in rack"),
            'not_found': ("Unknown wine", "Scan labels"),
            'label_front': ("Scan FRONT", "label now"),
            'label_back': ("Scan BACK", "label now"),
            'added': ("Bottle added", "to rack"),
            'removed': ("Bottle removed", "from rack"),
            'error': ("Error", "Check logs"),
            'offline': ("OFFLINE MODE", "Queued locally"),
            'syncing': ("Syncing...", "Please wait"),
            'reconciling': ("Checking rack", "Please wait..."),
            'position_err': ("Position", "unclear"),
            'calibrating': ("Calibrating", "Hold steady..."),
        }
        line1, line2 = messages.get(status, ("Unknown", "status"))
        self.show_message(line1, line2)

    def show_wine_added(self, wine_name, position):
        """Show wine added with position."""
        row, col = position
        self.show_message(
            wine_name[:16],
            f"Added R{row}C{col}"
        )

    def show_queue_status(self, queued_count):
        """Show offline queue status."""
        self.show_message(
            "OFFLINE MODE",
            f"{queued_count} queued"
        )

    def clear(self):
        """Clear the display."""
        self.lcd.clear()

    def backlight_on(self):
        """Turn backlight on."""
        self.lcd.backlight_enabled = True

    def backlight_off(self):
        """Turn backlight off."""
        self.lcd.backlight_enabled = False
```

**Installation on Pi:**
```bash
# Enable I2C
sudo raspi-config  # Interface Options → I2C → Enable

# Install dependencies
pip install RPLCD smbus2

# Find I2C address
i2cdetect -y 1
# Look for 27 or 3f in the output
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

### 4.5 Offline Queue System

When the server is unavailable, operations are queued locally and synced when connectivity returns.

```python
# pi_client/offline_queue.py

import json
import sqlite3
from datetime import datetime
from pathlib import Path
import asyncio

class OfflineQueue:
    """Queue operations when server is unavailable."""

    def __init__(self, db_path='/var/lib/wine-cellar/queue.db'):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database for queue."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS operation_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                synced_at TEXT,
                sync_attempts INTEGER DEFAULT 0,
                last_error TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def enqueue(self, operation_type, payload):
        """Add operation to queue."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            'INSERT INTO operation_queue (operation_type, payload, created_at) VALUES (?, ?, ?)',
            (operation_type, json.dumps(payload), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def get_pending(self):
        """Get all pending operations."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            'SELECT id, operation_type, payload, created_at FROM operation_queue WHERE synced_at IS NULL ORDER BY created_at'
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {'id': r[0], 'type': r[1], 'payload': json.loads(r[2]), 'created_at': r[3]}
            for r in rows
        ]

    def mark_synced(self, operation_id):
        """Mark operation as synced."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            'UPDATE operation_queue SET synced_at = ? WHERE id = ?',
            (datetime.now().isoformat(), operation_id)
        )
        conn.commit()
        conn.close()

    def mark_failed(self, operation_id, error):
        """Mark operation as failed with error."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            'UPDATE operation_queue SET sync_attempts = sync_attempts + 1, last_error = ? WHERE id = ?',
            (str(error), operation_id)
        )
        conn.commit()
        conn.close()

    def pending_count(self):
        """Get count of pending operations."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT COUNT(*) FROM operation_queue WHERE synced_at IS NULL')
        count = cursor.fetchone()[0]
        conn.close()
        return count


class SyncManager:
    """Manage syncing queued operations to server."""

    def __init__(self, api_client, queue, display):
        self.api = api_client
        self.queue = queue
        self.display = display
        self._is_online = True

    async def check_connectivity(self):
        """Check if server is reachable."""
        try:
            await self.api.health_check()
            return True
        except Exception:
            return False

    async def sync_pending(self):
        """Attempt to sync all pending operations."""
        if not await self.check_connectivity():
            return False

        pending = self.queue.get_pending()
        if not pending:
            return True

        self.display.show_status('syncing')

        for op in pending:
            try:
                if op['type'] == 'add_bottle':
                    await self.api.add_bottle(**op['payload'])
                elif op['type'] == 'remove_bottle':
                    await self.api.remove_bottle(**op['payload'])
                elif op['type'] == 'create_wine':
                    await self.api.create_wine(**op['payload'])
                elif op['type'] == 'rack_image':
                    await self.api.upload_rack_image(**op['payload'])

                self.queue.mark_synced(op['id'])

            except Exception as e:
                self.queue.mark_failed(op['id'], e)

        return True

    async def run_sync_loop(self, interval=60):
        """Run continuous sync loop."""
        while True:
            was_online = self._is_online
            self._is_online = await self.check_connectivity()

            # Just came back online
            if self._is_online and not was_online:
                await self.sync_pending()
                self.display.show_status('ready')

            # Show offline status if offline with queued items
            if not self._is_online:
                count = self.queue.pending_count()
                if count > 0:
                    self.display.show_queue_status(count)

            await asyncio.sleep(interval)
```

**Operation Types:**
| Type | Payload | Description |
|------|---------|-------------|
| `add_bottle` | `{wine_id, storage_id, row, column, detected_position}` | Add bottle to rack |
| `remove_bottle` | `{wine_id, position, barcode}` | Remove bottle from rack |
| `create_wine` | `{wine_data, storage_id, row, column}` | Create new wine and add bottle |
| `rack_image` | `{storage_id, image_base64, state, capture_type}` | Upload rack snapshot |

### 4.6 Tasks

- [ ] Create `pi_client/` package structure
- [ ] Implement `DisplayManager` for I2C LCD 1602
- [ ] Implement `CameraService` for image capture
- [ ] Implement `BarcodeScanner` service (USB)
- [ ] Implement `WorkflowController` for orchestration
- [ ] Create `APIClient` for server communication
- [ ] Implement `OfflineQueue` with SQLite storage
- [ ] Implement `SyncManager` for queue processing
- [ ] Add systemd service for auto-start
- [ ] Create installation script for Pi

---

## Phase 4b: Web UI for Position Review

**Goal**: Auto-detected bottle positions are highlighted on the web interface for user review and confirmation.

### 4b.1 Data Model Additions

```python
# wine_cellar/apps/storage/models.py (additions)

class StorageItem(models.Model):
    # ... existing fields ...

    # Position detection tracking
    position_auto_detected = models.BooleanField(default=False)
    position_confirmed = models.BooleanField(default=True)  # False for auto-detected
    position_detected_at = models.DateTimeField(null=True, blank=True)
    position_confirmed_at = models.DateTimeField(null=True, blank=True)
```

### 4b.2 API Endpoint for Confirmation

```python
# wine_cellar/apps/storage/views.py (additions)

@require_POST
@login_required
def confirm_bottle_position(request):
    """Confirm an auto-detected bottle position."""
    data = json.loads(request.body)
    item_id = data.get('item_id')

    item = get_object_or_404(
        StorageItem,
        id=item_id,
        storage__user=request.user,
        deleted=False
    )

    item.position_confirmed = True
    item.position_confirmed_at = timezone.now()
    item.save()

    return JsonResponse({'success': True})


@require_POST
@login_required
def correct_bottle_position(request):
    """Correct an incorrectly detected position."""
    data = json.loads(request.body)
    item_id = data.get('item_id')
    new_row = data.get('row')
    new_column = data.get('column')

    item = get_object_or_404(
        StorageItem,
        id=item_id,
        storage__user=request.user,
        deleted=False
    )

    # Check target is empty
    if StorageItem.objects.filter(
        storage=item.storage,
        row=new_row,
        column=new_column,
        deleted=False
    ).exists():
        return JsonResponse({
            'success': False,
            'error': 'Target position is occupied'
        }, status=400)

    item.row = new_row
    item.column = new_column
    item.position_confirmed = True
    item.position_confirmed_at = timezone.now()
    item.save()

    return JsonResponse({'success': True})


def get_unconfirmed_positions(request):
    """Get all bottles with unconfirmed positions."""
    items = StorageItem.objects.filter(
        storage__user=request.user,
        deleted=False,
        position_confirmed=False
    ).select_related('wine', 'storage')

    return JsonResponse({
        'items': [
            {
                'id': item.id,
                'wine_name': item.wine.name,
                'wine_id': item.wine.id,
                'storage_name': item.storage.name,
                'storage_id': item.storage.id,
                'row': item.row,
                'column': item.column,
                'detected_at': item.position_detected_at.isoformat() if item.position_detected_at else None,
            }
            for item in items
        ]
    })
```

### 4b.3 Storage Grid UI Updates

Update `storage_grid.tsx` to highlight unconfirmed positions:

```typescript
// Additions to storage_grid.tsx

interface StorageItem {
  row: number;
  column: number;
  wine: {
    id: number;
    name: string;
    vintage: number;
    wine_type: string;
    country: string;
    item_id: number;
  };
  position_confirmed: boolean;  // NEW
  position_detected_at: string | null;  // NEW
}

// In the cell rendering:
const getCellClass = (item: StorageItem | null) => {
  if (!item) return 'storage-cell empty';
  if (!item.position_confirmed) return 'storage-cell occupied unconfirmed';
  return 'storage-cell occupied';
};

// Unconfirmed cell has pulsing highlight
// CSS:
// .storage-cell.unconfirmed {
//   animation: pulse-highlight 2s infinite;
//   border: 2px solid #f59e0b;
// }

// Click handler for unconfirmed cells
const handleUnconfirmedClick = async (item: StorageItem) => {
  const confirm = window.confirm(
    `Confirm ${item.wine.name} at Row ${item.row}, Column ${item.column}?`
  );
  if (confirm) {
    await fetch('/api/storage/confirm-position/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
      },
      body: JSON.stringify({ item_id: item.wine.item_id }),
    });
    refreshGrid();
  }
};
```

### 4b.4 Dashboard Notification Banner

Add to homepage when unconfirmed positions exist:

```html
<!-- wine_cellar/templates/home.html additions -->

{% if unconfirmed_positions_count > 0 %}
<div class="alert alert-warning">
    <strong>{{ unconfirmed_positions_count }} bottle(s)</strong> have auto-detected positions awaiting confirmation.
    <a href="{% url 'storage:review-positions' %}">Review now</a>
</div>
{% endif %}
```

### 4b.5 Dedicated Review Page

```html
<!-- wine_cellar/templates/storage/review_positions.html -->

{% extends "base.html" %}

{% block content %}
<h1>Review Auto-Detected Positions</h1>

<p class="text-muted">
    These bottles were added via the Raspberry Pi scanner with automatically detected positions.
    Please confirm each position is correct, or drag to the correct location.
</p>

{% if not items %}
<div class="alert alert-success">
    All bottle positions have been confirmed!
</div>
{% else %}

<div class="table-responsive">
    <table class="table">
        <thead>
            <tr>
                <th>Wine</th>
                <th>Storage</th>
                <th>Detected Position</th>
                <th>Detected At</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for item in items %}
            <tr>
                <td>
                    <a href="{% url 'wine:detail' item.wine.id %}">
                        {{ item.wine.name }} {{ item.wine.vintage }}
                    </a>
                </td>
                <td>{{ item.storage.name }}</td>
                <td>Row {{ item.row }}, Column {{ item.column }}</td>
                <td>{{ item.position_detected_at|timesince }} ago</td>
                <td>
                    <button class="btn btn-sm btn-success" onclick="confirmPosition({{ item.id }})">
                        Confirm
                    </button>
                    <button class="btn btn-sm btn-outline-secondary" onclick="editPosition({{ item.id }})">
                        Move
                    </button>
                    <a href="{% url 'storage:detail' item.storage.id %}" class="btn btn-sm btn-outline-primary">
                        View Grid
                    </a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<button class="btn btn-success" onclick="confirmAll()">
    Confirm All Positions
</button>

{% endif %}
{% endblock %}
```

### 4b.6 Tasks

- [ ] Add `position_auto_detected`, `position_confirmed` fields to StorageItem
- [ ] Create migration for new fields
- [ ] Add `/api/storage/confirm-position/` endpoint
- [ ] Add `/api/storage/correct-position/` endpoint
- [ ] Add `/api/storage/unconfirmed-positions/` endpoint
- [ ] Update `storage_grid.tsx` with unconfirmed highlighting
- [ ] Add CSS for pulsing unconfirmed cells
- [ ] Add dashboard banner for unconfirmed positions
- [ ] Create dedicated review positions page
- [ ] Add "Confirm All" bulk action

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

## Technical Decisions (Confirmed)

| Decision | Choice | Notes |
|----------|--------|-------|
| Camera mounting | **Fixed** | Single fixed position viewing entire rack |
| Lighting | **Ambient** | Good existing lighting, no LED strip needed |
| Multiple racks | **Single** | Only one rack will have camera integration |
| Offline mode | **Yes** | Queue operations when server unavailable |
| Position confirmation | **Deferred to web** | Auto-detect, highlight on web for user review |
| Display type | **Freenove I2C LCD 1602** | 16x2 character display with I2C interface |

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

## Hardware Shopping List

| Item | Model/Notes | Est. Cost |
|------|-------------|-----------|
| Raspberry Pi | Pi 4 (4GB) or Pi 5 | $55-80 |
| Pi Camera | Module v2 or v3 | $25-35 |
| Display | Freenove I2C LCD 1602 | $8-12 |
| USB Barcode Scanner | Any HID-compatible | $20-40 |
| MicroSD Card | 32GB+ Class 10 | $10 |
| Power Supply | Official Pi PSU | $15 |
| Camera Mount | Fixed bracket/mount | $10-20 |
| Case | Optional, with camera slot | $15 |
| **Total** | | **~$160-220** |

---

## Next Steps

1. ~~Review and approve this plan~~ ✅
2. ~~Decide on technical decisions~~ ✅ (see table above)
3. Order Raspberry Pi hardware (see shopping list)
4. Begin Phase 1 (HTTPS improvements with mkcert)
5. Begin Phase 2 (Hardware API endpoints)
6. Parallel: Prototype OpenCV rack detection with test images
7. When Pi arrives: Implement Pi client application

---

## Appendix: Pi Wiring Diagram

```
Raspberry Pi 4/5
┌────────────────────────────────┐
│                                │
│  [Camera Port] ◄── Pi Camera   │
│                    (ribbon)    │
│                                │
│  GPIO Pins:                    │
│  ┌─────────────────────────┐   │
│  │ 3.3V (1) ─────► LCD VCC │   │
│  │ GND  (6) ─────► LCD GND │   │
│  │ SDA  (3) ─────► LCD SDA │   │  I2C LCD 1602
│  │ SCL  (5) ─────► LCD SCL │   │
│  └─────────────────────────┘   │
│                                │
│  USB Ports:                    │
│  ┌─────────────────────────┐   │
│  │ USB ◄──── Barcode       │   │  USB Barcode Scanner
│  │          Scanner        │   │  (HID keyboard mode)
│  └─────────────────────────┘   │
│                                │
└────────────────────────────────┘
```

**I2C Address Detection:**
```bash
# After connecting LCD, run:
sudo i2cdetect -y 1

# Expected output shows address (typically 27 or 3f):
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 20: -- -- -- -- -- -- -- 27 -- -- -- -- -- -- -- --
```
