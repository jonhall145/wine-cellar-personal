"""Vision-based wine label extraction service using Claude Vision API."""

import base64
import io
import logging
import re
import time
from typing import Any

import pycountry
from django.conf import settings
from PIL import Image

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
    """
    Log a vision extraction attempt for analysis.

    Args:
        user: The user who initiated the extraction
        image_count: Number of images sent for extraction
        raw_response: Raw response from the vision API
        extracted_data: Parsed extraction result
        confidence: Confidence level (high, medium, low)
        extracted_fields: List of fields that were successfully extracted
        errors: Any errors during extraction
        model_used: AI model used for extraction
        processing_time_ms: Time taken for the extraction in milliseconds
    """
    try:
        from wine_cellar.apps.wine.models import VisionExtractionLog

        VisionExtractionLog.objects.create(
            user=user,
            image_count=image_count,
            raw_response=raw_response,
            extracted_data=extracted_data,
            confidence=confidence,
            extracted_fields=extracted_fields,
            errors=errors,
            model_used=model_used,
            processing_time_ms=processing_time_ms,
        )
    except Exception as e:
        logger.warning(f"Failed to log vision extraction: {e}")


# Maximum image dimensions for Claude Vision API
# Claude supports up to 8000x8000 but recommends smaller for performance
MAX_IMAGE_DIMENSION = 1568  # Recommended max for good quality/speed balance
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB max per image


def resize_image_for_api(
    base64_image: str, max_dimension: int = MAX_IMAGE_DIMENSION
) -> str:
    """
    Resize an image if it exceeds the maximum dimensions.

    Args:
        base64_image: Base64-encoded image data
        max_dimension: Maximum width or height in pixels

    Returns:
        Base64-encoded resized image (or original if small enough)
    """
    try:
        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_image)

        # Check size first - if already small, skip processing
        if len(image_bytes) < MAX_IMAGE_SIZE_BYTES // 2:
            # Open to check dimensions
            img = Image.open(io.BytesIO(image_bytes))
            if img.width <= max_dimension and img.height <= max_dimension:
                return base64_image  # Already small enough

        # Open image
        img = Image.open(io.BytesIO(image_bytes))

        # Convert RGBA to RGB if necessary (JPEG doesn't support alpha)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Calculate new dimensions maintaining aspect ratio
        width, height = img.size
        if width > max_dimension or height > max_dimension:
            if width > height:
                new_width = max_dimension
                new_height = int(height * (max_dimension / width))
            else:
                new_height = max_dimension
                new_width = int(width * (max_dimension / height))

            # Resize with high quality
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.info(
                f"Resized image from {width}x{height} to {new_width}x{new_height}"
            )

        # Save to bytes with quality optimization
        output = io.BytesIO()
        quality = 85

        # Reduce quality if still too large
        img.save(output, format="JPEG", quality=quality, optimize=True)
        while output.tell() > MAX_IMAGE_SIZE_BYTES and quality > 30:
            output = io.BytesIO()
            quality -= 10
            img.save(output, format="JPEG", quality=quality, optimize=True)

        # Encode back to base64
        output.seek(0)
        resized_b64 = base64.b64encode(output.read()).decode("utf-8")

        logger.info(
            f"Image processed: {len(base64_image)} -> {len(resized_b64)} chars "
            f"(quality={quality})"
        )
        return resized_b64

    except Exception as e:
        logger.warning(f"Failed to resize image, using original: {e}")
        return base64_image


class WineVisionExtractor:
    """Service for extracting wine data from label images using Claude Vision API."""

    # Wine type mapping
    WINE_TYPE_MAP = {
        "red": "RE",
        "white": "WH",
        "rosé": "RO",
        "rose": "RO",
        "sparkling": "SP",
        "champagne": "SP",
        "prosecco": "SP",
        "cava": "SP",
        "dessert": "DE",
        "sweet": "DE",
        "fortified": "FO",
        "port": "FO",
        "sherry": "FO",
        "orange": "OR",
    }

    # Category (sweetness) mapping
    CATEGORY_MAP = {
        "dry": "DR",
        "semi-dry": "SD",
        "semi dry": "SD",
        "medium sweet": "MS",
        "medium-sweet": "MS",
        "sweet": "SW",
        "feinherb": "FH",
    }

    # Size mapping
    SIZE_MAP = {
        187: "PI",  # Piccolo
        375: "DE",  # Demi
        500: "HA",  # Half
        750: "ST",  # Standard
        1000: "LI",  # Liter
        1500: "MA",  # Magnum
        3000: "JE",  # Jeroboam
        4500: "RE",  # Rehoboam
    }

    # Wine region to country mappings for inference
    REGION_COUNTRY_MAP = {
        # France
        "bordeaux": "FR",
        "burgundy": "FR",
        "champagne": "FR",
        "rhône": "FR",
        "rhone": "FR",
        "loire": "FR",
        "alsace": "FR",
        "provence": "FR",
        "languedoc": "FR",
        "roussillon": "FR",
        "beaujolais": "FR",
        "jura": "FR",
        "savoie": "FR",
        "châteauneuf": "FR",
        "saint-emilion": "FR",
        "pomerol": "FR",
        "medoc": "FR",
        "sauternes": "FR",
        "chablis": "FR",
        "côte": "FR",
        "cote": "FR",
        # Italy
        "tuscany": "IT",
        "toscana": "IT",
        "piedmont": "IT",
        "piemonte": "IT",
        "veneto": "IT",
        "sicily": "IT",
        "sicilia": "IT",
        "puglia": "IT",
        "chianti": "IT",
        "barolo": "IT",
        "barbaresco": "IT",
        "brunello": "IT",
        "valpolicella": "IT",
        "soave": "IT",
        "prosecco": "IT",
        # Spain
        "rioja": "ES",
        "ribera del duero": "ES",
        "priorat": "ES",
        "rías baixas": "ES",
        "rias baixas": "ES",
        "jerez": "ES",
        "sherry": "ES",
        "penedès": "ES",
        "rueda": "ES",
        "toro": "ES",
        "navarra": "ES",
        "catalunya": "ES",
        # Portugal
        "douro": "PT",
        "dão": "PT",
        "dao": "PT",
        "alentejo": "PT",
        "vinho verde": "PT",
        "porto": "PT",
        "port": "PT",
        "madeira": "PT",
        # Germany
        "mosel": "DE",
        "rheingau": "DE",
        "pfalz": "DE",
        "rheinhessen": "DE",
        "baden": "DE",
        "franken": "DE",
        "nahe": "DE",
        # USA
        "napa": "US",
        "sonoma": "US",
        "paso robles": "US",
        "willamette": "US",
        "finger lakes": "US",
        "columbia valley": "US",
        "walla walla": "US",
        # Australia
        "barossa": "AU",
        "adelaide": "AU",
        "margaret river": "AU",
        "hunter valley": "AU",
        "yarra valley": "AU",
        "mclaren vale": "AU",
        # New Zealand
        "marlborough": "NZ",
        "hawke's bay": "NZ",
        "central otago": "NZ",
        # South Africa
        "stellenbosch": "ZA",
        "paarl": "ZA",
        "constantia": "ZA",
        # Chile
        "maipo": "CL",
        "colchagua": "CL",
        "casablanca": "CL",
        # Argentina
        "mendoza": "AR",
        "salta": "AR",
        "patagonia": "AR",
        # Austria
        "niederösterreich": "AT",
        "burgenland": "AT",
        "steiermark": "AT",
        # England/UK
        "surrey": "GB",
        "sussex": "GB",
        "kent": "GB",
        "hampshire": "GB",
    }

    # Appellation to country mappings
    APPELLATION_COUNTRY_MAP = {
        "aoc": "FR",
        "aop": "FR",
        "igp": "FR",
        "vin de france": "FR",
        "doc": "IT",
        "docg": "IT",
        "igt": "IT",
        "do": "ES",
        "doca": "ES",
        "vino de españa": "ES",
        "qmp": "DE",
        "qualitätswein": "DE",
        "ava": "US",
        "american viticultural area": "US",
    }

    def __init__(self):
        """Initialize the extractor."""
        self.api_key = settings.ANTHROPIC_API_KEY

    def extract_from_images(self, base64_images: list[str], user=None) -> dict:
        """
        Main extraction method supporting multiple images.

        Args:
            base64_images: List of base64-encoded image data
                (barcode, front label, back label)
            user: Optional user for logging the extraction

        Returns:
            dict with keys:
                - data: Extracted wine fields
                - confidence: 'high', 'medium', or 'low'
                - raw_text: OCR text for debugging
                - errors: List of error messages
                - extracted_fields: List of field names that were successfully extracted
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
                "ANTHROPIC_API_KEY not configured, using fallback extraction"
            )
            result["errors"].append("AI vision disabled - API key not configured")
            return self._fallback_regex_extraction("")

        try:
            # Call Claude Vision API with all images
            vision_result = self._call_claude_vision(base64_images)

            if vision_result.get("success"):
                result["data"] = vision_result["data"]
                result["confidence"] = vision_result.get("confidence", "medium")
                result["raw_text"] = vision_result.get("raw_text", "")
                result["extracted_fields"] = vision_result.get("extracted_fields", [])
            else:
                result["errors"].append(vision_result.get("error", "Unknown error"))
                logger.error(f"Vision extraction failed: {vision_result.get('error')}")

        except Exception as e:
            logger.exception("Error during vision extraction")
            result["errors"].append(f"Extraction error: {str(e)}")

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Log the extraction if user is provided
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

    def extract_from_image(self, base64_image: str, user=None) -> dict:
        """
        Legacy single-image extraction method.

        Args:
            base64_image: Base64-encoded image data
            user: Optional user for logging the extraction

        Returns:
            dict with extraction results
        """
        # Delegate to multi-image method with single image
        return self.extract_from_images([base64_image], user=user)

    def _call_claude_vision(self, base64_images: list[str]) -> dict:
        """
        Call Claude Vision API with structured prompt.

        Args:
            base64_images: List of base64-encoded image data

        Returns:
            dict with extraction results
        """
        try:
            import anthropic
        except ImportError:
            return {
                "success": False,
                "error": "anthropic package not installed",
            }

        try:
            client = anthropic.Anthropic(api_key=self.api_key)

            # Construct the prompt for structured extraction
            prompt = self._build_extraction_prompt()

            # Build content array with all images (resized for API)
            content = []
            image_labels = ["barcode", "front label", "back label"]
            for idx, base64_image in enumerate(base64_images):
                # Resize image if too large
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

            # Add the extraction prompt at the end
            content.append(
                {
                    "type": "text",
                    "text": prompt,
                }
            )

            # Call the API
            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": content,
                    }
                ],
            )

            # Parse the response
            response_text = response.content[0].text
            logger.info(f"Vision API response:\n{response_text}")

            # Extract structured data from response
            extracted_data = self._parse_claude_response(response_text)

            return {
                "success": True,
                "data": extracted_data["data"],
                "confidence": extracted_data["confidence"],
                "raw_text": response_text,
                "extracted_fields": extracted_data["extracted_fields"],
            }

        except Exception as e:
            logger.exception("Error calling Claude Vision API")
            return {
                "success": False,
                "error": f"API call failed: {str(e)}",
            }

    def _build_extraction_prompt(self) -> str:
        """Build the structured extraction prompt for Claude."""
        return """You are analyzing wine label images. I've provided \
multiple images (barcode, front label, back label) to help you extract \
comprehensive information. Analyze ALL images to extract as much \
information as possible and return it in a structured format.

Please extract the following information if visible in ANY of the images:

1. **Wine Name**: The main name/title of the wine
2. **Wine Type**: red, white, rosé, sparkling, dessert, fortified, or orange
3. **Vintage**: The year (4-digit number between 1900-2030)
4. **Country**: The country of origin. Look for:
   - "Product of..." or "Produit de..." text
   - Country names anywhere on the label
   - Appellation indicators (AOC/AOP=France, DOC/DOCG=Italy, DO=Spain, etc.)
   - Region names that indicate country (Bordeaux=France, Rioja=Spain, Tuscany=Italy)
   Return as country name or ISO code
5. **Region/Subregion**: Geographic region (e.g., "Bordeaux", "Tuscany", "Napa Valley")
6. **Grapes/Varieties**: List of grape varieties (e.g., Cabernet Sauvignon, Merlot)
7. **Vineyard/Producer**: The winery or producer name
8. **ABV**: Alcohol by volume percentage (as a number, e.g., 13.5)
9. **Volume**: Bottle size in ml (e.g., 750, 375, 1500)
10. **Sweetness**: dry, semi-dry, medium sweet, sweet, or feinherb
11. **Barcode**: If visible in the barcode image
12. **Label Bounds**: For each image containing a wine label, estimate the \
bounding box of the main label as percentages of image dimensions (0-100). \
Format: x1,y1,x2,y2 where (x1,y1) is top-left and (x2,y2) is bottom-right.

Return your response in this exact format:

```
NAME: [wine name or "not found"]
TYPE: [wine type or "not found"]
VINTAGE: [year or "not found"]
COUNTRY: [ISO code or country name or "not found"]
REGION: [region or "not found"]
GRAPES: [grape1, grape2, ... or "not found"]
VINEYARD: [vineyard name or "not found"]
ABV: [number or "not found"]
VOLUME: [ml as number or "not found"]
SWEETNESS: [sweetness level or "not found"]
BARCODE: [barcode or "not found"]
CONFIDENCE: [high/medium/low]
LABEL_BOUNDS_FRONT: [x1,y1,x2,y2 or "not found"]
LABEL_BOUNDS_BACK: [x1,y1,x2,y2 or "not found"]
```

**Important**:
- Combine information from ALL images provided
- If you cannot read or find a field in any image, write "not found"
- For grapes, use comma-separated list
- For confidence: "high" if confident, "medium" if some unclear, "low" if hard to read
- For label bounds, estimate the rectangular area containing the main label
- Be precise and only extract what you can actually see on the labels
"""

    def _parse_claude_response(self, response_text: str) -> dict:
        """
        Parse Claude's structured response into wine fields.

        Args:
            response_text: Response from Claude API

        Returns:
            dict with parsed data and metadata
        """
        data = {}
        extracted_fields = []

        # Extract each field using regex
        patterns = {
            "name": r"NAME:\s*(.+?)(?:\n|$)",
            "wine_type": r"TYPE:\s*(.+?)(?:\n|$)",
            "vintage": r"VINTAGE:\s*(.+?)(?:\n|$)",
            "country": r"COUNTRY:\s*(.+?)(?:\n|$)",
            "subregion": r"REGION:\s*(.+?)(?:\n|$)",
            "grapes": r"GRAPES:\s*(.+?)(?:\n|$)",
            "vineyard": r"VINEYARD:\s*(.+?)(?:\n|$)",
            "abv": r"ABV:\s*(.+?)(?:\n|$)",
            "volume": r"VOLUME:\s*(.+?)(?:\n|$)",
            "sweetness": r"SWEETNESS:\s*(.+?)(?:\n|$)",
            "barcode": r"BARCODE:\s*(.+?)(?:\n|$)",
            "label_bounds_front": r"LABEL_BOUNDS_FRONT:\s*(.+?)(?:\n|$)",
            "label_bounds_back": r"LABEL_BOUNDS_BACK:\s*(.+?)(?:\n|$)",
        }

        for field, pattern in patterns.items():
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value.lower() != "not found" and value:
                    # Process the value based on field type
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
        if "country" not in data and "subregion" in data:
            inferred_country = self._infer_country_from_region(data)
            if inferred_country:
                data["country"] = inferred_country
                extracted_fields.append("country")

        # Try to match subregion to an Appellation for map coordinates
        if "subregion" in data:
            appellation = self._match_appellation(
                data["subregion"], data.get("country")
            )
            if appellation:
                data["appellation"] = appellation
                extracted_fields.append("appellation")

        return {
            "data": data,
            "confidence": confidence,
            "extracted_fields": extracted_fields,
        }

    def _process_field_value(self, field: str, value: str) -> Any:
        """
        Process and validate a field value.

        Args:
            field: Field name
            value: Raw value from extraction

        Returns:
            Processed value or None if invalid
        """
        value = value.strip()

        if field == "wine_type":
            # Map to model choice
            value_lower = value.lower()
            for key, code in self.WINE_TYPE_MAP.items():
                if key in value_lower:
                    return code
            return None

        elif field == "vintage":
            # Extract year
            year_match = re.search(r"\b(19\d{2}|20[0-2]\d)\b", value)
            if year_match:
                return int(year_match.group(1))
            return None

        elif field == "country":
            # Strategy 1: Already a 2-letter ISO code
            if len(value) == 2 and value.isalpha():
                return value.upper()

            # Strategy 2: Direct country name lookup
            try:
                country = pycountry.countries.search_fuzzy(value)[0]
                return country.alpha_2
            except (LookupError, AttributeError):
                pass

            # Strategy 3: Check for region-to-country mapping
            value_lower = value.lower()
            for region, country_code in self.REGION_COUNTRY_MAP.items():
                if region in value_lower:
                    return country_code

            # Strategy 4: Check for appellation indicators
            for appellation, country_code in self.APPELLATION_COUNTRY_MAP.items():
                if appellation in value_lower:
                    return country_code

            return None

        elif field == "grapes":
            # Split by comma and clean
            grapes = [g.strip() for g in value.split(",")]
            return [g for g in grapes if g]

        elif field == "vineyard":
            return value

        elif field == "abv":
            # Extract number
            abv_match = re.search(r"(\d+\.?\d*)", value)
            if abv_match:
                abv = float(abv_match.group(1))
                if 5.0 <= abv <= 25.0:  # Reasonable range
                    return abv
            return None

        elif field == "volume":
            # Extract ml and map to size code
            vol_match = re.search(r"(\d+)", value)
            if vol_match:
                ml = int(vol_match.group(1))
                # Find closest size
                for size_ml, code in self.SIZE_MAP.items():
                    if abs(ml - size_ml) < 50:  # Within 50ml tolerance
                        return code
            return None

        elif field == "sweetness":
            # Map to category
            value_lower = value.lower()
            for key, code in self.CATEGORY_MAP.items():
                if key in value_lower:
                    return code
            return None

        elif field == "name":
            # Clean up wine name
            return value

        elif field == "subregion":
            return value

        elif field == "appellation":
            # This field is populated by post-processing, not direct extraction
            return value

        elif field == "barcode":
            # Only return if it looks like a barcode (numbers)
            if re.match(r"^\d+$", value):
                return value
            return None

        elif field in ("label_bounds_front", "label_bounds_back"):
            # Parse bounding box coordinates: x1,y1,x2,y2
            # Values should be percentages (0-100)
            bounds_match = re.match(
                r"(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*"
                r"(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)",
                value,
            )
            if bounds_match:
                try:
                    x1 = float(bounds_match.group(1))
                    y1 = float(bounds_match.group(2))
                    x2 = float(bounds_match.group(3))
                    y2 = float(bounds_match.group(4))
                    # Validate ranges (0-100) and order (x1<x2, y1<y2)
                    if (
                        0 <= x1 <= 100
                        and 0 <= y1 <= 100
                        and 0 <= x2 <= 100
                        and 0 <= y2 <= 100
                        and x1 < x2
                        and y1 < y2
                    ):
                        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
                except (ValueError, IndexError):
                    pass
            return None

        return value

    def _infer_country_from_region(self, extracted_data: dict) -> str | None:
        """
        Infer country from subregion if country wasn't extracted.

        Args:
            extracted_data: Dictionary of extracted wine data

        Returns:
            ISO alpha-2 country code or None
        """
        if "country" in extracted_data:
            return None  # Already have country

        subregion = extracted_data.get("subregion", "")
        if not subregion:
            return None

        subregion_lower = subregion.lower()

        # Check region mappings
        for region, country_code in self.REGION_COUNTRY_MAP.items():
            if region in subregion_lower:
                return country_code

        return None

    def _match_appellation(
        self, subregion: str, country: str | None = None
    ) -> int | None:
        """
        Try to match extracted subregion to an Appellation record.

        Args:
            subregion: Extracted subregion/region name
            country: Optional country code to narrow matches

        Returns:
            Appellation ID if matched, else None
        """
        try:
            from wine_cellar.apps.wine.models import Appellation

            subregion_lower = subregion.lower().strip()

            # Build query - try exact match first (case-insensitive)
            query = Appellation.objects.filter(name__iexact=subregion)
            if country:
                query = query.filter(country=country)

            appellation = query.first()
            if appellation:
                return appellation.pk

            # Try contains match if no exact match
            query = Appellation.objects.filter(name__icontains=subregion_lower)
            if country:
                query = query.filter(country=country)

            appellation = query.first()
            if appellation:
                return appellation.pk

            # Try matching subregion within appellation name
            for app in Appellation.objects.all():
                if app.name.lower() in subregion_lower:
                    if not country or app.country == country:
                        return app.pk

            return None

        except Exception as e:
            logger.warning(f"Error matching appellation for '{subregion}': {e}")
            return None

    def _fallback_regex_extraction(self, text: str) -> dict:
        """
        Fallback to basic regex extraction if API is unavailable.

        Args:
            text: OCR text to parse

        Returns:
            dict with extracted data
        """
        data = {}
        extracted_fields = []

        # Try to extract vintage year (4 digit number between 1900-2030)
        year_match = re.search(r"\b(19\d{2}|20[0-2]\d)\b", text)
        if year_match:
            data["vintage"] = int(year_match.group(1))
            extracted_fields.append("vintage")

        # Try to extract ABV
        abv_match = re.search(r"(\d+\.?\d*)\s*%?\s*(alc|abv|vol)", text, re.IGNORECASE)
        if abv_match:
            abv = float(abv_match.group(1))
            if 5.0 <= abv <= 25.0:
                data["abv"] = abv
                extracted_fields.append("abv")

        # Try to extract volume
        vol_match = re.search(r"(\d+)\s*(ml|cl|l)\b", text, re.IGNORECASE)
        if vol_match:
            vol = int(vol_match.group(1))
            unit = vol_match.group(2).lower()
            if unit == "cl":
                vol = vol * 10
            elif unit == "l":
                vol = vol * 1000

            # Map to size code
            for size_ml, code in self.SIZE_MAP.items():
                if abs(vol - size_ml) < 50:
                    data["size"] = code
                    extracted_fields.append("size")
                    break

        return {
            "data": data,
            "confidence": "low",
            "raw_text": text,
            "errors": ["Using fallback extraction (limited data)"],
            "extracted_fields": extracted_fields,
        }
