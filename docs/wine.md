# Wine

## Overview

A **Wine** represents a unique wine type or label — identified by key attributes like grapes, vintage, vinyard.  
Wines are *templates* for real bottles, which reference them when stored in the cellar.

### Wine vs Bottle

It’s important to distinguish between a **Wine** and a **Bottle**:

| Concept | Description |
|----------|--------------|
| **Wine** | Metadata about a particular label or type of wine |
| **Bottle** | A specific instance of a wine in your cellar inventory |

A single Wine record may have many bottles stored across different shelves or racks.

### Example

You might have:

- `Wine`: Château Margaux 2015  
- 12 `Bottle` entries linked to it, each with a defined storage location.

This separation allows you to:

- Keep clean records of your cellar contents
- Manage bottles individually
- Track vintages, tasting notes, and inventory history

---

## Recording Wine Consumption

### Drink Records

When you consume a bottle, you can create a **Drink Record** to track:

- **Date consumed** - When you drank the wine
- **Tasting notes** - Your detailed impressions
- **Rating** - How you rated this particular drinking experience (0-3 stars)
- **Shared with** - People you shared the bottle with
- **Occasion** - The special event or occasion
- **Specific bottle** - Which exact bottle was consumed (optional)

### Bottle Selection

When recording a drink, you can optionally select which specific bottle from your inventory was consumed:

1. Navigate to the wine detail page
2. Click "Record a Drink"
3. Select a bottle from the dropdown (shows storage location)
4. Fill in your tasting notes and other details
5. Submit the form

**What happens:**
- The drink record is created with a reference to the specific bottle
- The bottle is automatically marked as consumed (deleted)
- Your stock count decreases automatically
- The bottle remains in your history for reference

**Benefits:**
- Links tasting experiences to specific bottles
- Automatic inventory management
- Track which bottles from different purchases or storage locations you've consumed
- Better history and record-keeping

**Note:** Selecting a bottle is optional. You can still record a drink without linking it to a specific bottle in inventory.

---

### Related Topics
- [Storage](storage.md): How and where bottles are organized in your cellar

