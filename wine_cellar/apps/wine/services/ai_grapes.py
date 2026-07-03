"""AI grape inference service for wines with missing grape data."""

import base64
import logging
import re

import anthropic
import pycountry
from django.conf import settings

from wine_cellar.apps.wine.models import Grape, ImageType, Wine
from wine_cellar.apps.wine.services.grape_normalization import normalize_grape_list
from wine_cellar.apps.wine.services.vision_extraction import resize_image_for_api

logger = logging.getLogger(__name__)


class WineAIGrapeService:
    """Infer and persist grape varieties for wines."""

    DEFAULT_MODEL = "claude-haiku-4-5"

    @classmethod
    def refresh_grapes(cls, wine_id: int, *, include_images: bool = True) -> bool:
        """Populate missing grapes for a wine."""
        if not settings.ANTHROPIC_API_KEY:
            logger.info(
                (
                    "Skipping AI grape inference for wine %s: "
                    "ANTHROPIC_API_KEY not configured"
                ),
                wine_id,
            )
            return False

        wine = Wine.objects.with_related().filter(pk=wine_id, deleted=False).first()
        if wine is None:
            logger.warning(
                "Skipping AI grape inference: wine %s was not found", wine_id
            )
            return False

        if wine.grapes.exists():
            return False

        try:
            grape_names, _confidence = cls.identify_grapes(
                wine, include_images=include_images
            )
        except anthropic.APIError:
            logger.exception("AI grape inference failed for wine %s", wine.pk)
            return False

        if not grape_names:
            return False

        grapes = []
        for grape_name in grape_names:
            grape, _created = Grape.objects.get_or_create(
                name=grape_name,
                user=wine.user,
                defaults={"household": wine.household},
            )
            grapes.append(grape)

        wine.grapes.add(*grapes)
        return True

    @classmethod
    def identify_grapes(
        cls, wine: Wine, *, include_images: bool = True
    ) -> tuple[list[str], str]:
        """Return inferred grapes and model confidence for a wine."""
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=getattr(settings, "WINE_AI_GRAPES_MODEL", cls.DEFAULT_MODEL),
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": cls._build_content(wine, include_images=include_images),
                }
            ],
        )

        response_text = response.content[0].text
        return cls.parse_response(response_text)

    @staticmethod
    def build_prompt(wine: Wine) -> str:
        """Build a prompt to identify likely grape varieties."""
        country_name = "Unknown"
        if wine.country:
            country = pycountry.countries.get(alpha_2=wine.country)
            if country:
                country_name = country.name

        wine_type_display = (
            wine.get_wine_type_display() if wine.wine_type else "Unknown"
        )

        return (
            "You are a wine expert. Given the following wine information, "
            "identify the most likely grape varieties used to make this wine.\n\n"
            f"Wine Name: {wine.name}\n"
            f"Wine Type: {wine_type_display}\n"
            f"Country: {country_name}\n"
            f"Region: {wine.subregion or 'Unknown'}\n"
            f"Comment: {wine.comment or 'None'}\n\n"
            "Rules:\n"
            "- Return ONLY grape variety names you are confident about\n"
            '- Use full canonical names in title case (e.g., "Cabernet Sauvignon")\n'
            "- For well-known regional wines, infer grapes from the "
            "appellation/region\n"
            "- If the wine name itself is a grape variety, include it\n"
            "- If you cannot determine the grapes with reasonable confidence, "
            'return "not found"\n'
            "- Do not guess wildly - only return grapes you would bet on\n\n"
            "Return in this exact format:\n"
            "GRAPES: grape1, grape2, grape3\n"
            "CONFIDENCE: high/medium/low"
        )

    @staticmethod
    def parse_response(response_text: str) -> tuple[list[str], str]:
        """Parse a model response into normalized grapes and confidence."""
        grapes = []
        confidence = "low"

        grape_match = re.search(
            r"GRAPES:\s*(.+?)(?:\n|$)", response_text, re.IGNORECASE
        )
        if grape_match:
            raw = grape_match.group(1).strip()
            if raw.lower() != "not found":
                grapes = normalize_grape_list(raw.split(","))

        conf_match = re.search(
            r"CONFIDENCE:\s*(.+?)(?:\n|$)", response_text, re.IGNORECASE
        )
        if conf_match:
            parsed_confidence = conf_match.group(1).strip().lower()
            if parsed_confidence in ("high", "medium", "low"):
                confidence = parsed_confidence

        return grapes, confidence

    @classmethod
    def _build_content(cls, wine: Wine, *, include_images: bool) -> list[dict]:
        content = []
        if include_images:
            content.extend(cls._build_image_content(wine))
        content.append({"type": "text", "text": cls.build_prompt(wine)})
        return content

    @staticmethod
    def _build_image_content(wine: Wine) -> list[dict]:
        content = []
        images = sorted(
            wine.wineimage_set.all(),
            key=lambda image: (
                {
                    ImageType.LABEL_FRONT: 0,
                    ImageType.LABEL_BACK: 1,
                }.get(image.image_type, 99),
                image.pk,
            ),
        )[:2]

        for image in images:
            try:
                with image.image.open("rb") as file_obj:
                    image_data = file_obj.read()
                resized = resize_image_for_api(
                    base64.b64encode(image_data).decode("utf-8")
                )
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": resized,
                        },
                    }
                )
            except Exception:
                logger.warning(
                    "Could not load image %s for AI grape inference on wine %s",
                    image.pk,
                    wine.pk,
                    exc_info=True,
                )

        return content
