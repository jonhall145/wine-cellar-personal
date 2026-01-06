# Database Models

## Overview

This document provides comprehensive documentation for all Django models in the Wine Cellar application. The models are organized into three main Django apps: **Wine**, **Storage**, and **User**.

---

## Table of Contents

- [Base Models](#base-models)
- [Wine App Models](#wine-app-models)
- [Storage App Models](#storage-app-models)
- [User App Models](#user-app-models)
- [Model Relationships](#model-relationships)

---

## Base Models

### UserContentModel

**Location**: `wine_cellar/apps/wine/models.py:17`

Abstract base model that provides common fields for all user-owned content.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `user` | ForeignKey | Reference to User model | CASCADE, nullable, indexed |
| `created` | DateTimeField | Auto-set on creation | Auto-now-add, indexed |
| `modified` | DateTimeField | Auto-updated on save | Auto-now |

**Usage**: All models that belong to users inherit from this base model to ensure consistent tracking of ownership and timestamps.

---

## Wine App Models

### Wine

**Location**: `wine_cellar/apps/wine/models.py:204`

Core model representing a unique wine type or label. This is the template for actual bottles stored in the cellar.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `name` | CharField(100) | Wine name | Required |
| `barcode` | CharField(100) | Barcode identifier | Optional |
| `wine_type` | CharField(2) | Type of wine (Red, White, etc.) | Required, choices from WineType |
| `category` | CharField(2) | Sweetness category | Optional, choices from Category |
| `grapes` | ManyToManyField | Grape varieties used | Links to Grape model |
| `attributes` | ManyToManyField | Wine characteristics | Links to Attribute model |
| `food_pairings` | ManyToManyField | Recommended food pairings | Links to FoodPairing model |
| `abv` | FloatField | Alcohol by volume percentage | Optional |
| `size` | ForeignKey | Bottle size | SET_NULL, links to Size model |
| `vintage` | PositiveIntegerField | Year of production | Optional, min 1900, indexed |
| `drink_by` | DateField | Recommended consumption date | Optional, indexed |
| `comment` | CharField(250) | Additional notes | Optional |
| `rating` | PositiveIntegerField | Wine rating | Optional, 0-10 range |
| `country` | CharField(3) | Country of origin | Required, ISO alpha-2 code (max 3 chars), indexed |
| `subregion` | CharField(100) | Wine region/subregion | Optional |
| `vineyard` | ManyToManyField | Producer vineyards | Links to Vineyard model |
| `source` | ManyToManyField | Purchase sources | Links to Source model |
| `price` | DecimalField(6,2) | Reference price | Optional |
| `rrp` | DecimalField(6,2) | Recommended retail price | Optional |

**Properties**:
- `get_absolute_url()`: Returns detail view URL
- `get_vineyards`: Newline-separated vineyard names
- `get_grapes`: Comma-separated grape names
- `get_sources`: Comma-separated source names
- `get_attributes`: Newline-separated attributes
- `get_price_with_currency`: Formatted price with currency symbol
- `get_rrp_with_currency`: Formatted RRP with currency symbol
- `get_average_price_with_currency`: Average price across all bottles
- `get_food_pairings`: Newline-separated food pairings
- `get_type`: Human-readable wine type label
- `get_category`: Human-readable category label
- `total_stock`: Count of non-deleted bottles
- `get_stock`: QuerySet of non-deleted storage items
- `image`: URL to first wine image or default
- `image_thumbnail`: URL to thumbnail or full image
- `image_thumbnails`: List of thumbnail URLs in order
- `country_name`: Full country name from ISO code
- `country_icon`: Country flag emoji

**Constraints**:
- Unique constraint on: `name`, `wine_type`, `abv`, `size`, `vintage`, `country`, `user`

**Related Models**:
- Has many `WineImage` records (one-to-many)
- Has many `StorageItem` records (one-to-many)
- Has many `DrinkRecord` records (one-to-many)
- Has many `DrinkingWindowAlert` records (one-to-many)
- Has many `ReorderReminder` records (one-to-many)

---

### WineImage

**Location**: `wine_cellar/apps/wine/models.py:394`

Stores multiple images for each wine with type classification.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `image` | ImageField | Full-size image file | Required, user directory path |
| `thumbnail` | ImageField | Thumbnail version | Optional, user directory path |
| `wine` | ForeignKey | Parent wine | CASCADE, required |
| `user` | ForeignKey | Owner | SET_NULL, nullable |
| `image_type` | CharField(3) | Image category | Choices: Front, Back, Label Front, Label Back |

**Image Types** (from `ImageType` enum):
- `FR` - Front: Bottle front view
- `BA` - Back: Bottle back view
- `LF` - Label Front: Close-up of front label
- `LB` - Label Back: Close-up of back label

---

### Grape

**Location**: `wine_cellar/apps/wine/models.py:111`

Represents grape varieties used in wines.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `name` | CharField(100) | Grape variety name | Required |

**Constraints**:
- Unique constraint on: `name`, `user`

**Usage**: Linked to wines via many-to-many relationship to track grape composition.

---

### Vineyard

**Location**: `wine_cellar/apps/wine/models.py:128`

Stores information about wine producers and vineyards.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `name` | CharField(100) | Vineyard name | Required |
| `website` | CharField(100) | Website URL | Optional |
| `region` | CharField(250) | Geographic region | Optional |
| `country` | CharField(3) | Country code | Optional, ISO alpha-2 code (max 3 chars) |

**Constraints**:
- Unique constraint on: `name`, `country`, `region`, `user`

---

### Size

**Location**: `wine_cellar/apps/wine/models.py:89`

Defines bottle size options.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `name` | CharField(2) | Size code | Required, choices from SizeChoices |

**Size Options** (from `SizeChoices` enum):
- `PI` - Piccolo (187ml)
- `DE` - Demi (375ml)
- `HA` - Half (500ml)
- `ST` - Standard (750ml) - Default
- `LI` - Liter (1L)
- `MA` - Magnum (1.5L)
- `JE` - Jeroboam (3L)
- `RE` - Rehoboam (4.5L)

**Constraints**:
- Unique constraint on: `name`, `user`

---

### FoodPairing

**Location**: `wine_cellar/apps/wine/models.py:153`

Represents foods that pair well with wines.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `name` | CharField(100) | Food name | Required |

**Constraints**:
- Unique constraint on: `name`, `user`

**Usage**: Linked to wines to suggest complementary food pairings.

---

### Attribute

**Location**: `wine_cellar/apps/wine/models.py:170`

Stores wine characteristics and descriptors (e.g., "Oak-aged", "Full-bodied", "Fruity").

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `name` | CharField(100) | Attribute name | Required |

**Constraints**:
- Unique constraint on: `name`, `user`

---

### Source

**Location**: `wine_cellar/apps/wine/models.py:187`

Tracks where wines were purchased or acquired.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `name` | CharField(250) | Source name | Required |

**Constraints**:
- Unique constraint on: `name`, `user`

**Examples**: "Local Wine Shop", "Online Retailer", "Vineyard Direct", "Gift"

---

### DrinkRecord

**Location**: `wine_cellar/apps/wine/models.py:425`

Records when and how a bottle was consumed.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `wine` | ForeignKey | Wine consumed | CASCADE, required |
| `date_consumed` | DateField | Consumption date | Required |
| `tasting_notes` | TextField | Detailed tasting notes | Optional |
| `rating` | PositiveIntegerField | Rating for this tasting | Optional, 0-10 range |
| `shared_with` | CharField(250) | People shared with | Optional |
| `occasion` | CharField(100) | Special occasion | Optional |

**Ordering**: By `date_consumed` descending (most recent first)

**Purpose**: Tracks drinking history and allows retrospective tasting notes separate from the wine's general rating.

---

### Wishlist

**Location**: `wine_cellar/apps/wine/models.py:454`

Tracks wines the user wants to purchase.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `name` | CharField(100) | Wine name | Required |
| `wine_type` | CharField(2) | Wine type | Optional, choices from WineType |
| `country` | CharField(3) | Country | Optional, ISO alpha-2 code (max 3 chars) |
| `subregion` | CharField(100) | Region | Optional |
| `vintage` | PositiveIntegerField | Desired vintage | Optional |
| `price_limit` | DecimalField(6,2) | Maximum price | Optional |
| `notes` | TextField | Additional notes | Optional |
| `priority` | PositiveIntegerField | Priority level | Default 1, range 1-5 |
| `purchased` | BooleanField | Marked as bought | Default False |

**Ordering**: By `priority` descending, then `name` ascending

**Purpose**: Shopping list and wine acquisition planning.

---

### BottleNote

**Location**: `wine_cellar/apps/wine/models.py:491`

Dated notes for tracking a specific bottle's evolution over time.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `storage_item` | ForeignKey | Specific bottle | CASCADE, required, related_name='notes' |
| `note_date` | DateField | Date of note | Required |
| `note` | TextField | Note content | Required |

**Ordering**: By `note_date` descending (most recent first)

**Purpose**: Track how individual bottles age and change, separate from general wine comments.

---

### DrinkingWindowAlert

**Location**: `wine_cellar/apps/wine/models.py:509`

Alerts for wines approaching their optimal drinking window.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `wine` | ForeignKey | Wine to alert about | CASCADE, required |
| `alert_date` | DateField | When to alert | Required |
| `message` | CharField(250) | Alert message | Optional |
| `is_read` | BooleanField | Marked as read | Default False |

**Ordering**: By `alert_date` ascending (soonest first)

**Purpose**: Notify users to drink wines before they pass their peak.

---

### ReorderReminder

**Location**: `wine_cellar/apps/wine/models.py:527`

Reminds users to reorder wines when stock is low.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `wine` | ForeignKey | Wine to monitor | CASCADE, required |
| `min_stock` | PositiveIntegerField | Minimum bottle count | Default 1 |
| `is_active` | BooleanField | Reminder enabled | Default True |

**Constraints**:
- Unique constraint on: `wine`, `user`

**Purpose**: Automated inventory management - alerts when stock drops below threshold.

---

## Storage App Models

### Storage

**Location**: `wine_cellar/apps/storage/models.py:7`

Represents physical storage locations (racks, shelves, fridges) with optional grid layout.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `name` | CharField(100) | Storage name | Required |
| `description` | TextField | Detailed description | Optional |
| `location` | CharField(100) | Physical location | Required |
| `rows` | PositiveIntegerField | Number of rows | Default 0 |
| `columns` | PositiveIntegerField | Number of columns | Default 0 |

**Properties**:
- `total_slots`: Total capacity (rows × columns)
- `used_slots`: Count of bottles currently stored
- `is_full`: True if used_slots >= total_slots
- `is_slot_occupied(row, column)`: Check if specific position is taken
- `get_wines`: QuerySet of non-deleted bottles, ordered by position

**Storage Modes**:
- **Unstructured** (rows=0, columns=0): No grid, unlimited capacity
- **Structured** (rows>0, columns>0): Fixed grid with specific positions

**Example**:
```python
# Unstructured storage (e.g., wine fridge)
fridge = Storage(name="Wine Fridge", location="Kitchen", rows=0, columns=0)

# Structured storage (e.g., 4x6 rack)
rack = Storage(name="Main Rack", location="Cellar", rows=4, columns=6)
```

---

### StorageItem

**Location**: `wine_cellar/apps/storage/models.py:45`

Represents an individual bottle stored in a location. This is the actual inventory item.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `storage` | ForeignKey | Storage location | CASCADE, required, related_name='items' |
| `wine` | ForeignKey | Wine type | CASCADE, required |
| `row` | PositiveIntegerField | Row position | Optional (for grid storage) |
| `column` | PositiveIntegerField | Column position | Optional (for grid storage) |
| `deleted` | BooleanField | Soft delete flag | Default False, indexed |
| `price` | DecimalField(6,2) | Purchase price | Optional |
| `is_gift` | BooleanField | Received as gift | Default False |
| `gift_from` | CharField(100) | Gift giver name | Optional |
| `occasion` | CharField(100) | Gift occasion | Optional |

**Usage**:
- Each `StorageItem` represents one physical bottle
- Multiple bottles of the same wine each have their own `StorageItem`
- `deleted=True` marks consumed or removed bottles (soft delete for history)
- `row` and `column` only used for structured storage
- Individual pricing allows tracking of bottles bought at different times/prices

**Related via**:
- `storage.items.all()` - All items in a storage location
- `wine.storageitem_set.all()` - All bottles of a specific wine

---

## User App Models

### UserSettings

**Location**: `wine_cellar/apps/user/models.py:7`

Stores per-user preferences and configuration.

**Fields**:
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `user` | OneToOneField | User account | CASCADE, required, related_name='user_settings' |
| `language` | CharField(7) | Preferred language | Choices from LANGUAGES, default from settings |
| `currency` | CharField(3) | Preferred currency | Choices from CURRENCIES, default EUR |
| `notifications` | BooleanField | Enable notifications | Default True |

**Relationship**: One-to-one with Django's User model

**Supported Currencies** (configured in settings):
- EUR, USD, GBP, and others as configured

**Purpose**: Customize display formats, language, and notification preferences per user.

---

## Enumerations

### WineType

**Location**: `wine_cellar/apps/wine/models.py:40`

| Code | Label |
|------|-------|
| `WH` | White |
| `RE` | Red |
| `RO` | Rose |
| `SP` | Sparkling |
| `DE` | Dessert |
| `FO` | Fortified |
| `OR` | Orange |

---

### Category (Sweetness)

**Location**: `wine_cellar/apps/wine/models.py:50`

| Code | Label |
|------|-------|
| `DR` | Dry |
| `SD` | Semi-Dry |
| `MS` | Medium Sweet |
| `SW` | Sweet |
| `FH` | Feinherb |

---

## Model Relationships

### Relationship Diagram

```
User (Django Auth)
  ├─── UserSettings (1:1)
  │
  ├─── Wine (1:N)
  │     ├─── WineImage (1:N)
  │     ├─── StorageItem (1:N) ──→ Storage (N:1)
  │     ├─── DrinkRecord (1:N)
  │     ├─── DrinkingWindowAlert (1:N)
  │     ├─── ReorderReminder (1:N)
  │     │
  │     └─── Many-to-Many:
  │           ├─── Grape (N:M)
  │           ├─── Vineyard (N:M)
  │           ├─── Attribute (N:M)
  │           ├─── FoodPairing (N:M)
  │           └─── Source (N:M)
  │
  ├─── Wishlist (1:N)
  │
  ├─── Storage (1:N)
  │     └─── StorageItem (1:N) ──→ Wine (N:1)
  │           └─── BottleNote (1:N)
  │
  └─── Supporting Models (1:N each)
        ├─── Grape
        ├─── Vineyard
        ├─── Size
        ├─── Attribute
        ├─── FoodPairing
        └─── Source
```

---

## Key Design Patterns

### 1. Wine vs Bottle Separation
- **Wine**: Template/metadata about a wine type
- **StorageItem**: Individual bottles in inventory
- Allows: Multiple bottles of same wine, individual pricing, location tracking

### 2. User Isolation
- All models extend `UserContentModel` or have `user` ForeignKey
- Ensures multi-tenant data isolation
- Each user sees only their own data

### 3. Soft Deletes
- `StorageItem.deleted` instead of hard deletion
- Preserves history for consumed bottles
- Maintains referential integrity

### 4. Flexible Storage
- Supports both structured (grid) and unstructured (freeform) storage
- `rows=0, columns=0` = unstructured
- `rows>0, columns>0` = structured grid

### 5. Rich Metadata
- Many-to-many relationships for flexible categorization
- Choice fields with enums for consistency
- Optional fields for gradual data entry

---

## Database Constraints

### Unique Constraints

| Model | Unique Fields |
|-------|---------------|
| **Wine** | name, wine_type, abv, size, vintage, country, user |
| **Grape** | name, user |
| **Vineyard** | name, country, region, user |
| **FoodPairing** | name, user |
| **Attribute** | name, user |
| **Source** | name, user |
| **Size** | name, user |
| **ReorderReminder** | wine, user |

### Indexes

- `created` and `modified` on all UserContentModel descendants
- `vintage` on Wine
- `drink_by` on Wine
- `country` on Wine
- `deleted` on StorageItem

---

## Migration Notes

### Size Field Migration
The `Size` model was previously a decimal field (liters). A mapping constant `SIZE_LITERS_TO_CODE` exists in `wine_cellar/apps/wine/models.py:76` for migrating historical data:

```python
SIZE_LITERS_TO_CODE = {
    0.1875: "PI",  # Piccolo
    0.375: "DE",   # Demi
    0.5: "HA",     # Half
    0.75: "ST",    # Standard
    1.0: "LI",     # Liter
    1.5: "MA",     # Magnum
    3.0: "JE",     # Jeroboam
    4.5: "RE",     # Rehoboam
}
```

---

## Related Documentation

- [Wine Concepts](wine.md) - High-level wine vs bottle explanation
- [Storage Concepts](storage.md) - Storage organization patterns
- [agents.md](../agents.md) - Full project context including database schema
- [CLAUDE.md](../CLAUDE.md) - AI agent capabilities and testing tools

---

*Generated: 2026-01-05*
