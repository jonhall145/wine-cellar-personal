"""Vision-based wine label extraction service using Claude Vision API."""

import base64
import logging
import re
from typing import Any

import pycountry
from django.conf import settings

logger = logging.getLogger(__name__)


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

    def __init__(self):
        """Initialize the extractor."""
        self.api_key = settings.ANTHROPIC_API_KEY

    def extract_from_image(self, base64_image: str) -> dict:
        """
        Main extraction method.

        Args:
            base64_image: Base64-encoded image data

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

        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not configured, using fallback extraction")
            result["errors"].append("AI vision disabled - API key not configured")
            return self._fallback_regex_extraction("")

        try:
            # Call Claude Vision API
            vision_result = self._call_claude_vision(base64_image)

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

        return result

    def _call_claude_vision(self, base64_image: str) -> dict:
        """
        Call Claude Vision API with structured prompt.

        Args:
            base64_image: Base64-encoded image data

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

            # Call the API
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": base64_image,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )

            # Parse the response
            response_text = response.content[0].text

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
        return """You are analyzing a wine label image. Extract as much information as possible from the label and return it in a structured format.

Please extract the following information if visible:

1. **Wine Name**: The main name/title of the wine
2. **Wine Type**: red, white, rosé, sparkling, dessert, fortified, or orange
3. **Vintage**: The year (4-digit number between 1900-2030)
4. **Country**: The country of origin (provide ISO alpha-2 code if possible, e.g., FR, IT, ES, US)
5. **Region/Subregion**: Geographic region (e.g., "Bordeaux", "Tuscany", "Napa Valley")
6. **Grapes/Varieties**: List of grape varieties (e.g., Cabernet Sauvignon, Merlot)
7. **Vineyard/Producer**: The winery or producer name
8. **ABV**: Alcohol by volume percentage (as a number, e.g., 13.5)
9. **Volume**: Bottle size in ml (e.g., 750, 375, 1500)
10. **Sweetness**: dry, semi-dry, medium sweet, sweet, or feinherb
11. **Barcode**: If visible

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
```

**Important**:
- If you cannot read or find a field, write "not found"
- For grapes, use comma-separated list
- For confidence, use "high" if you're very confident in most fields, "medium" if some fields are unclear, "low" if the label is hard to read
- Be precise and only extract what you can actually see on the label
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
            # Try to get ISO alpha-2 code
            # If already a 2-letter code
            if len(value) == 2 and value.isalpha():
                return value.upper()

            # Try to find country by name
            try:
                country = pycountry.countries.search_fuzzy(value)[0]
                return country.alpha_2
            except (LookupError, AttributeError):
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

        elif field == "barcode":
            # Only return if it looks like a barcode (numbers)
            if re.match(r"^\d+$", value):
                return value
            return None

        return value

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
