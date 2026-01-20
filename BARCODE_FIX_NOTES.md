# Barcode Scanning Fix Notes

## Issue
Users reported that scanning a barcode for an existing bottle often failed to detect the existing record.

## Root Cause
The matching logic in `WineScannedView` was performing a strict exact string match (`Wine.objects.filter(barcode=code)`). This failed when:
1.  **Whitespace**: The stored barcode had leading/trailing whitespace (e.g., `" 123 "` vs `"123"`).
2.  **Format Mismatches (UPC-A vs EAN-13)**:
    *   UPC-A barcodes are 12 digits.
    *   EAN-13 barcodes are 13 digits.
    *   Often, a UPC-A barcode like `123456789012` is stored as an EAN-13 `0123456789012` (leading zero).
    *   Scanners might read either format depending on configuration, leading to mismatches (e.g., scanned `123...` vs stored `0123...`).

## Solution implemented
Refactored the barcode matching logic into a centralized, robust method within `BarcodeScanner` service.

### Changes
1.  **`wine_cellar/apps/wine/services/barcode_service.py`**:
    *   Added `get_wine_object_by_barcode(self, barcode, user)`:
        *   Strips whitespace from input.
        *   Generates variants to check: exact match, with leading zero (if 12 chars), without leading zero (if 13 chars starting with 0).
        *   Queries database for any of these variants.
        *   Falls back to a case-insensitive containment search (`icontains`) to handle "dirty" database records (e.g., stored with whitespace), verifying the match in Python.
    *   Updated `find_wine_by_barcode` to use this new method.

2.  **`wine_cellar/apps/wine/views.py`**:
    *   Updated `WineScannedView.dispatch` to use `scanner.get_wine_object_by_barcode(code, request.user)` instead of the raw ORM filter.

## Verification
*   Added temporary reproduction tests covering:
    *   Exact match (passed)
    *   Leading zero mismatch (fixed)
    *   Whitespace mismatch (fixed)
*   Ran existing `test_barcode_service.py` to ensure no regressions.
