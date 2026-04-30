# API Documentation

This document describes the internal API endpoints used by Wine Cellar.

## Authentication

Most endpoints require authentication via Django session cookies. Hardware API endpoints use token-based authentication via the `X-Api-Token` header.

### REST API (Bearer Token)

The REST API at `/rest/` uses Bearer token authentication. An admin-scoped API key is stored in `.env.prod` (gitignored) as `WINE_CELLAR_API_TOKEN`.

```bash
source .env.prod
curl -H "Authorization: Bearer $WINE_CELLAR_API_TOKEN" http://localhost:80/rest/wines/
```

Manage keys with Django management commands:
- **Create:** `python manage.py create_api_key --name "Name" --user admin --household 1 --scope admin`
- **List:** `python manage.py list_api_keys`
- **Revoke:** `python manage.py revoke_api_key <prefix_or_name> [--delete]`

Scopes: `read` (GET only), `write` (read + POST/PUT/PATCH/DELETE), `admin` (full access).

---

## Wine Endpoints

### POST /wine/extract-vision/

Extract wine information from uploaded label images using AI vision.

**Authentication:** Session (login required)
**Rate Limit:** 10 requests/minute per user

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image_front_label` | File | No | Front label image |
| `image_back_label` | File | No | Back label image |
| `image_front` | File | No | Front bottle image |
| `image_back` | File | No | Back bottle image |

At least one image is required. Max size: 10MB per image.

**Response (success):**
```json
{
  "success": true,
  "wine_data": {
    "name": "Chateau Example",
    "vintage": 2019,
    "wine_type": "RD",
    "country": "FR",
    "grapes": ["Cabernet Sauvignon", "Merlot"]
  },
  "match_type": "vision",
  "extracted_fields": ["name", "vintage", "wine_type"]
}
```

**Response (barcode match):**
```json
{
  "success": true,
  "wine_data": {...},
  "match_type": "barcode",
  "wine_id": 123
}
```

**Error responses:**
- `400`: Image too large or invalid request
- `405`: Method not allowed (must be POST)
- `500`: Server error

---

### POST /wine/scan-barcode/

Scan barcode from a captured image (no AI, uses pyzbar).

**Authentication:** Session (login required)
**Rate Limit:** 30 requests/minute per user

**Request:** `application/json`
```json
{
  "image": "data:image/png;base64,..."
}
```

**Response (success):**
```json
{
  "success": true,
  "barcodes": ["1234567890123"],
  "barcode": "1234567890123"
}
```

**Response (no barcode found):**
```json
{
  "success": false,
  "barcodes": [],
  "message": "No barcode detected"
}
```

**Error responses:**
- `400`: Invalid JSON or no image data
- `405`: Method not allowed
- `500`: Server error

---

## Storage Endpoints

### GET /api/storage/grid-data/

Get storage grid data for the React storage grid component.

**Authentication:** Session (login required)

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `storage_id` | int | Optional. Storage ID to select. Defaults to first storage. |

**Response:**
```json
{
  "storages": [
    {
      "id": 1,
      "name": "Wine Rack",
      "rows": 5,
      "columns": 10,
      "used_slots": 12,
      "total_slots": 50,
      "utilization_percent": 24,
      "items": [
        {
          "row": 1,
          "column": 2,
          "wine": {
            "id": 42,
            "name": "Chateau Example",
            "vintage": 2019,
            "wine_type": "Red",
            "country": "France",
            "item_id": 101
          }
        }
      ]
    }
  ],
  "current_storage_id": 1
}
```

---

### POST /api/storage/move-bottle/

Move a bottle to a new position in storage.

**Authentication:** Session (login required)

**Request:** `application/json`
```json
{
  "item_id": 101,
  "target_storage_id": 1,
  "target_row": 2,
  "target_column": 5
}
```

**Response (success):**
```json
{
  "success": true,
  "message": "Moved to Wine Rack (2, 5)"
}
```

**Error responses:**
- `400`: Missing fields, invalid position, or position occupied
- `404`: Bottle or storage not found
- `500`: Server error

---

## Health Check

### GET /health/

Health check endpoint for monitoring and container orchestration.

**Authentication:** None required

**Response (healthy):**
```json
{
  "status": "ok"
}
```

**Response (unhealthy):** Status 503
```json
{
  "status": "unhealthy"
}
```

---

## Hardware API (Raspberry Pi)

These endpoints are used by Raspberry Pi devices for wine rack monitoring.

### Authentication

All hardware API endpoints require token authentication:
```
X-Api-Token: <device_api_token>
```

### GET /api/v1/health/

Check API health and verify token.

**Response:**
```json
{
  "status": "ok",
  "version": "0.3.0"
}
```

---

### POST /api/v1/devices/register/

Register a new hardware device.

**Request:**
```json
{
  "device_id": "rpi-001",
  "device_type": "rack_monitor",
  "name": "Kitchen Rack Monitor"
}
```

**Response:**
```json
{
  "success": true,
  "device_id": "rpi-001",
  "message": "Device registered successfully"
}
```

---

### POST /api/v1/position-change/

Report a detected position change (bottle added/removed).

**Request:**
```json
{
  "rack_id": 1,
  "row": 2,
  "column": 5,
  "change_type": "added",
  "image_data": "base64...",
  "confidence": 0.95
}
```

**Response:**
```json
{
  "success": true,
  "review_id": 42,
  "requires_review": true
}
```

---

### GET /api/v1/pending-reviews/

Get pending position reviews for user approval.

**Response:**
```json
{
  "reviews": [
    {
      "id": 42,
      "rack_name": "Kitchen Rack",
      "row": 2,
      "column": 5,
      "change_type": "added",
      "detected_at": "2024-01-15T10:30:00Z",
      "confidence": 0.95
    }
  ]
}
```

---

### POST /api/v1/reviews/{review_id}/approve/

Approve a pending position change review.

**Response:**
```json
{
  "success": true
}
```

---

### POST /api/v1/reviews/{review_id}/reject/

Reject a pending position change review.

**Response:**
```json
{
  "success": true
}
```

---

### GET /api/v1/wines/barcode/{barcode}/

Look up wine by barcode.

**Response (found):**
```json
{
  "id": 42,
  "name": "Chateau Example",
  "vintage": 2019,
  "wine_type": "RD",
  "country": "FR"
}
```

**Response (not found):** Status 404
```json
{
  "error": "Wine not found"
}
```

---

### POST /api/v1/wines/from-labels/

Create a new wine from label images using AI vision.

**Request:** `multipart/form-data`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `front_label` | File | Yes | Front label image |
| `back_label` | File | No | Back label image |
| `storage_id` | int | No | Storage to add bottle to |
| `row` | int | No | Row position |
| `column` | int | No | Column position |

**Response:**
```json
{
  "success": true,
  "wine_id": 42,
  "wine": {
    "name": "Chateau Example",
    "vintage": 2019
  }
}
```

---

### GET /api/v1/storage/racks/{rack_id}/positions/

Get all positions in a storage rack.

**Response:**
```json
{
  "rack_id": 1,
  "rack_name": "Kitchen Rack",
  "rows": 5,
  "columns": 10,
  "positions": [
    {
      "row": 1,
      "column": 1,
      "occupied": true,
      "wine_id": 42,
      "wine_name": "Chateau Example"
    }
  ]
}
```

---

### POST /api/v1/storage/add/

Add a wine to a storage position.

**Request:**
```json
{
  "wine_id": 42,
  "rack_id": 1,
  "row": 2,
  "column": 5
}
```

**Response:**
```json
{
  "success": true,
  "item_id": 101
}
```

---

### POST /api/v1/storage/remove/

Remove a wine from a storage position.

**Request:**
```json
{
  "rack_id": 1,
  "row": 2,
  "column": 5
}
```

**Response:**
```json
{
  "success": true
}
```

---

## Error Handling

All endpoints return errors in a consistent format:

```json
{
  "error": "Description of what went wrong"
}
```

Common HTTP status codes:
- `400` - Bad Request (invalid input)
- `401` - Unauthorized (missing or invalid authentication)
- `404` - Not Found (resource doesn't exist)
- `405` - Method Not Allowed
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error
