"""Vision-based whisky label extraction service using Claude Vision API."""

import logging
import re
import time
from typing import Any

import pycountry
from django.conf import settings

from wine_cellar.apps.wine.services.vision_extraction import resize_image_for_api

logger = logging.getLogger(__name__)


def log_extraction(
    user,
    image_count: int,
    raw_response: str,
    extracted_data: dict,
    confidence: str,
    extracted_fields: list,
    errors: list | None = None,
    model_used: str = "claude-haiku-4-5",
    processing_time_ms: int | None = None,
):
    """Log a whisky vision extraction attempt for analysis."""
    try:
        from wine_cellar.apps.whisky.models import WhiskyVisionExtractionLog

        WhiskyVisionExtractionLog.objects.create(
            user=user,
            image_count=image_count,
            raw_response=raw_response,
            extracted_data=extracted_data,
            confidence=confidence,
            extracted_fields=extracted_fields,
            errors=errors or [],
            model_used=model_used,
            processing_time_ms=processing_time_ms,
        )
    except Exception as e:
        logger.warning(f"Failed to log whisky vision extraction: {e}")


class WhiskyVisionExtractor:
    """Service for extracting whisky data from label images using Claude Vision API."""

    # Whisky type mapping
    WHISKY_TYPE_MAP = {
        "single malt": "SM",
        "blended malt": "BM",
        "blended": "BL",
        "single grain": "SG",
    }

    # Peated level mapping
    PEATED_LEVEL_MAP = {
        "peated": "PE",
        "heavily peated": "PE",
        "smoky": "PE",
        "unpeated": "UP",
    }

    # Size mapping (ml -> BottleSize value)
    SIZE_MAP = {
        50: "0.05",
        100: "0.10",
        200: "0.20",
        350: "0.35",
        500: "0.50",
        700: "0.70",
        1000: "1.00",
        1500: "1.50",
    }

    # Region to country mappings for whisky
    REGION_COUNTRY_MAP = {
        # Scotland
        "speyside": "XS",
        "islay": "XS",
        "highland": "XS",
        "lowland": "XS",
        "campbeltown": "XS",
        "islands": "XS",
        "scotland": "XS",
        # USA
        "kentucky": "US",
        "tennessee": "US",
        # Ireland
        "ireland": "IE",
        # Japan
        "japan": "JP",
        "hokkaido": "JP",
        # India
        "india": "IN",
        # Taiwan
        "taiwan": "TW",
        # Australia
        "tasmania": "AU",
        "australia": "AU",
        # Canada
        "canada": "CA",
        # England
        "england": "XE",
        # Wales
        "wales": "XW",
    }

    def __init__(self):
        """Initialize the extractor."""
        self.api_key = settings.ANTHROPIC_API_KEY

    def extract_from_images(self, base64_images: list[str], user=None) -> dict:
        """
        Main extraction method supporting multiple images.

        Args:
            base64_images: List of base64-encoded image data
            user: Optional user for logging the extraction

        Returns:
            dict with keys:
                - data: Extracted whisky fields
                - confidence: 'high', 'medium', or 'low'
                - raw_text: Raw text for debugging
                - errors: List of error messages
                - extracted_fields: List of field names successfully extracted
        """
        result = {
            "data": {},
            "confidence": "low",
            "raw_text": "",
            "errors": [],
            "extracted_fields": [],
        }

        start_time = time.time()

        if not self.api_key:
            logger.warning(
                "ANTHROPIC_API_KEY not configured, vision extraction disabled"
            )
            result["errors"].append("AI vision disabled - API key not configured")
            return result

        try:
            vision_result = self._call_claude_vision(base64_images)

            if vision_result.get("success"):
                result["data"] = vision_result["data"]
                result["confidence"] = vision_result.get("confidence", "medium")
                result["raw_text"] = vision_result.get("raw_text", "")
                result["extracted_fields"] = vision_result.get("extracted_fields", [])
            else:
                result["errors"].append(vision_result.get("error", "Unknown error"))
                logger.error(f"Vision extraction failed: {vision_result.get('error')}")

        except Exception:
            logger.exception("Error during whisky vision extraction")
            result["errors"].append("Extraction error")

        processing_time_ms = int((time.time() - start_time) * 1000)

        if user:
            log_extraction(
                user=user,
                image_count=len(base64_images),
                raw_response=result.get("raw_text", ""),
                extracted_data=result.get("data", {}),
                confidence=result.get("confidence", "low"),
                extracted_fields=result.get("extracted_fields", []),
                errors=result.get("errors") if result.get("errors") else None,
                processing_time_ms=processing_time_ms,
            )

        return result

    def _call_claude_vision(self, base64_images: list[str]) -> dict:
        """Call Claude Vision API with structured prompt."""
        try:
            import anthropic
        except ImportError:
            return {
                "success": False,
                "error": "anthropic package not installed",
            }

        try:
            client = anthropic.Anthropic(api_key=self.api_key)

            prompt = self._build_extraction_prompt()

            content = []
            image_labels = ["barcode", "front label", "back label"]
            for idx, base64_image in enumerate(base64_images):
                resized_image = resize_image_for_api(base64_image)

                label = (
                    image_labels[idx] if idx < len(image_labels) else f"image {idx+1}"
                )
                content.append({"type": "text", "text": f"[{label.upper()}]"})
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": resized_image,
                        },
                    }
                )

            content.append({"type": "text", "text": prompt})

            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=2048,
                messages=[{"role": "user", "content": content}],
            )

            response_text = response.content[0].text
            logger.info(f"Whisky Vision API response:\n{response_text}")

            extracted_data = self._parse_claude_response(response_text)

            return {
                "success": True,
                "data": extracted_data["data"],
                "confidence": extracted_data["confidence"],
                "raw_text": response_text,
                "extracted_fields": extracted_data["extracted_fields"],
            }

        except Exception:
            logger.exception("Error calling Claude Vision API for whisky")
            return {
                "success": False,
                "error": "API call failed",
            }

    def _build_extraction_prompt(self) -> str:
        """Build the structured extraction prompt for Claude."""
        return """You are analyzing whisky label images. I've provided \
multiple images (barcode, front label, back label) to help you extract \
comprehensive information. Analyze ALL images to extract as much \
information as possible and return it in a structured format.

Please extract the following information if visible in ANY of the images:

1. **NAME**: The main name/title of the whisky
2. **WHISKY_TYPE**: single malt, blended malt, blended, or single grain
3. **DISTILLERY**: The distillery name
4. **AGE_STATEMENT**: Age in years (number only, e.g. 12)
5. **ABV**: Alcohol by volume percentage (as a number, e.g., 46.0)
6. **COUNTRY**: The country of origin. Look for:
   - "Product of Scotland" = Scotland
   - "Scotch Whisky" = Scotland
   - "Irish Whiskey" = Ireland
   - "Bourbon" or "Tennessee" = USA
   - Return as country name
7. **REGION**: Whisky region (e.g., Speyside, Islay, Highland, Kentucky)
8. **PEATED_LEVEL**: peated, heavily peated, smoky, or unpeated
9. **CASK_TYPE**: Cask/barrel type (e.g., Bourbon, Sherry (Oloroso), Port)
10. **SIZE**: Bottle size in ml (e.g., 700, 50, 1000)
11. **VINTAGE_YEAR**: Year distilled (4-digit number)
12. **BOTTLED_YEAR**: Year bottled (4-digit number)
13. **CASK_NUMBER**: Cask number if shown
14. **BATCH_NUMBER**: Batch number if shown
15. **BOTTLE_NUMBER**: Bottle number if shown (e.g., 123/500)
16. **BOTTLER**: Independent bottler name (if not official bottling)
17. **BOTTLER_SERIES**: Series name from bottler (e.g., "Connoisseurs Choice")
18. **BARCODE**: If visible in the barcode image

Return your response in this exact format:

```
NAME: [whisky name or "not found"]
WHISKY_TYPE: [type or "not found"]
DISTILLERY: [distillery or "not found"]
AGE_STATEMENT: [years or "not found"]
ABV: [number or "not found"]
COUNTRY: [country name or "not found"]
REGION: [region or "not found"]
PEATED_LEVEL: [level or "not found"]
CASK_TYPE: [cask type or "not found"]
SIZE: [ml or "not found"]
VINTAGE_YEAR: [year or "not found"]
BOTTLED_YEAR: [year or "not found"]
CASK_NUMBER: [number or "not found"]
BATCH_NUMBER: [number or "not found"]
BOTTLE_NUMBER: [number or "not found"]
BOTTLER: [bottler name or "not found"]
BOTTLER_SERIES: [series or "not found"]
BARCODE: [barcode or "not found"]
CONFIDENCE: [high/medium/low]
```

**Important**:
- Combine information from ALL images provided
- If you cannot read or find a field in any image, write "not found"
- For confidence: "high" if confident, "medium" if some unclear, "low" if hard to read
- Be precise and only extract what you can actually see on the labels
"""

    def _parse_claude_response(self, response_text: str) -> dict:
        """Parse Claude's structured response into whisky fields."""
        data = {}
        extracted_fields = []

        patterns = {
            "name": r"NAME:\s*(.+?)(?:\n|$)",
            "whisky_type": r"WHISKY_TYPE:\s*(.+?)(?:\n|$)",
            "distillery": r"DISTILLERY:\s*(.+?)(?:\n|$)",
            "age_statement": r"AGE_STATEMENT:\s*(.+?)(?:\n|$)",
            "abv": r"ABV:\s*(.+?)(?:\n|$)",
            "country": r"COUNTRY:\s*(.+?)(?:\n|$)",
            "region": r"REGION:\s*(.+?)(?:\n|$)",
            "peated_level": r"PEATED_LEVEL:\s*(.+?)(?:\n|$)",
            "cask_type": r"CASK_TYPE:\s*(.+?)(?:\n|$)",
            "size": r"SIZE:\s*(.+?)(?:\n|$)",
            "vintage_year": r"VINTAGE_YEAR:\s*(.+?)(?:\n|$)",
            "bottled_year": r"BOTTLED_YEAR:\s*(.+?)(?:\n|$)",
            "cask_number": r"CASK_NUMBER:\s*(.+?)(?:\n|$)",
            "batch_number": r"BATCH_NUMBER:\s*(.+?)(?:\n|$)",
            "bottle_number": r"BOTTLE_NUMBER:\s*(.+?)(?:\n|$)",
            "bottler": r"BOTTLER:\s*(.+?)(?:\n|$)",
            "bottler_series": r"BOTTLER_SERIES:\s*(.+?)(?:\n|$)",
            "barcode": r"BARCODE:\s*(.+?)(?:\n|$)",
        }

        for field, pattern in patterns.items():
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value.lower() != "not found" and value:
                    processed_value = self._process_field_value(field, value)
                    if processed_value is not None:
                        data[field] = processed_value
                        extracted_fields.append(field)

        # Extract confidence
        confidence_match = re.search(
            r"CONFIDENCE:\s*(.+?)(?:\n|$)", response_text, re.IGNORECASE
        )
        confidence = "medium"
        if confidence_match:
            conf_value = confidence_match.group(1).strip().lower()
            if conf_value in ["high", "medium", "low"]:
                confidence = conf_value

        # Try to infer country from region if not found
        if "country" not in data and "region" in data:
            inferred_country = self._infer_country_from_region(data["region"])
            if inferred_country:
                data["country"] = inferred_country
                extracted_fields.append("country")

        return {
            "data": data,
            "confidence": confidence,
            "extracted_fields": extracted_fields,
        }

    def _process_field_value(self, field: str, value: str) -> Any:
        """Process and validate a field value."""
        value = value.strip()

        if field == "whisky_type":
            value_lower = value.lower()
            for key, code in self.WHISKY_TYPE_MAP.items():
                if key in value_lower:
                    return code
            return None

        elif field == "age_statement":
            age_match = re.search(r"(\d+)", value)
            if age_match:
                age = int(age_match.group(1))
                if 1 <= age <= 100:
                    return age
            return None

        elif field == "abv":
            abv_match = re.search(r"(\d+\.?\d*)", value)
            if abv_match:
                abv = float(abv_match.group(1))
                if 20.0 <= abv <= 75.0:
                    return abv
            return None

        elif field == "country":
            # Custom whisky country codes
            value_lower = value.lower()

            custom_map = {
                "scotland": "XS",
                "scotch": "XS",
                "england": "XE",
                "wales": "XW",
            }
            for name, code in custom_map.items():
                if name in value_lower:
                    return code

            # Already a 2-letter ISO code
            if len(value) == 2 and value.isalpha():
                return value.upper()

            # Standard pycountry lookup
            try:
                country = pycountry.countries.search_fuzzy(value)[0]
                return country.alpha_2
            except (LookupError, AttributeError):
                pass

            # Check region-to-country mapping
            for region, country_code in self.REGION_COUNTRY_MAP.items():
                if region in value_lower:
                    return country_code

            return None

        elif field == "peated_level":
            value_lower = value.lower()
            for key, code in self.PEATED_LEVEL_MAP.items():
                if key in value_lower:
                    return code
            return None

        elif field == "size":
            vol_match = re.search(r"(\d+)", value)
            if vol_match:
                ml = int(vol_match.group(1))
                for size_ml, code in self.SIZE_MAP.items():
                    if abs(ml - size_ml) < 50:
                        return code
            return None

        elif field in ("vintage_year", "bottled_year"):
            year_match = re.search(r"\b(19\d{2}|20[0-2]\d)\b", value)
            if year_match:
                return int(year_match.group(1))
            return None

        elif field == "barcode":
            if re.match(r"^\d+$", value):
                return value
            return None

        elif field in (
            "name",
            "distillery",
            "cask_type",
            "cask_number",
            "batch_number",
            "bottle_number",
            "bottler",
            "bottler_series",
            "region",
        ):
            return value

        return value

    def _infer_country_from_region(self, region: str) -> str | None:
        """Infer country from region name."""
        if not region:
            return None

        region_lower = region.lower()
        for region_name, country_code in self.REGION_COUNTRY_MAP.items():
            if region_name in region_lower:
                return country_code

        return None
