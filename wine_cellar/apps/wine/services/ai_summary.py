"""AI-generated wine summary service."""

import logging
from urllib.parse import urlparse

import anthropic
from django.conf import settings
from django.utils import timezone

from wine_cellar.apps.wine.models import Wine

logger = logging.getLogger(__name__)


class WineAISummaryService:
    """Generate and persist sourced AI summaries for wines."""

    DEFAULT_MODEL = "claude-sonnet-4-6"
    WEB_SEARCH_TOOL = {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 4,
    }
    SYSTEM_PROMPT = (
        "You are a wine research assistant for a personal cellar app. "
        "Use web search to verify the wine before writing. "
        "Write a concise 2-4 sentence summary focused on producer, region, style, "
        "and any vintage-specific context you can verify. "
        "Do not speculate. Omit claims you cannot support with citations."
    )

    @classmethod
    def refresh_summary(cls, wine_id: int) -> bool:
        """Refresh the stored AI summary for a wine."""
        if not settings.ANTHROPIC_API_KEY:
            logger.info(
                (
                    "Skipping AI summary generation for wine %s: "
                    "ANTHROPIC_API_KEY not configured"
                ),
                wine_id,
            )
            return False

        wine = Wine.objects.with_related().filter(pk=wine_id, deleted=False).first()
        if wine is None:
            logger.warning(
                "Skipping AI summary generation: wine %s was not found", wine_id
            )
            return False

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        try:
            response = client.messages.create(
                model=getattr(settings, "WINE_AI_SUMMARY_MODEL", cls.DEFAULT_MODEL),
                max_tokens=500,
                system=cls.SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": cls._build_prompt(wine),
                    }
                ],
                tools=[cls.WEB_SEARCH_TOOL],
            )
        except anthropic.APIError:
            logger.exception("AI summary generation failed for wine %s", wine.pk)
            return False

        summary_text = cls._extract_summary_text(response.content)
        summary_sources = cls._extract_summary_sources(response.content)
        if not summary_text or not summary_sources:
            logger.warning(
                (
                    "Skipping AI summary save for wine %s: "
                    "response was missing text or citations"
                ),
                wine.pk,
            )
            return False

        wine.ai_summary = summary_text
        wine.ai_summary_sources = summary_sources
        wine.ai_summary_generated_at = timezone.now()
        wine.ai_summary_model = getattr(response, "model", "") or getattr(
            settings, "WINE_AI_SUMMARY_MODEL", cls.DEFAULT_MODEL
        )
        wine.save(
            update_fields=[
                "ai_summary",
                "ai_summary_sources",
                "ai_summary_generated_at",
                "ai_summary_model",
            ]
        )
        return True

    @classmethod
    def _build_prompt(cls, wine: Wine) -> str:
        preferred_urls = cls._collect_preferred_urls(wine)
        details = [
            f"Wine name: {wine.name}",
            f"Vintage: {wine.vintage or 'Unknown'}",
            f"Type: {wine.get_type}",
            f"Country: {wine.country_name}",
            f"Subregion: {wine.subregion or 'Unknown'}",
            (
                f"Appellation: "
                f"{wine.appellation.name if wine.appellation else 'Unknown'}"
            ),
            f"Grapes: {wine.get_grapes or 'Unknown'}",
            f"Vineyard/producer: {wine.get_vineyards or 'Unknown'}",
            f"Cellar notes: {wine.comment or 'None'}",
        ]
        if preferred_urls:
            details.append(
                "Prioritize these known wine-specific URLs if they are relevant:\n- "
                + "\n- ".join(preferred_urls)
            )
        details.append(
            (
                "Return only the summary text. Every factual claim must be backed "
                "by cited web-search results."
            )
        )
        return "\n".join(details)

    @staticmethod
    def _collect_preferred_urls(wine: Wine) -> list[str]:
        urls: list[str] = []
        if wine.price_url:
            urls.append(wine.price_url)
        for vineyard in wine.vineyard.all():
            if vineyard.website:
                urls.append(vineyard.website)
        for source in wine.source.all():
            if source.url:
                urls.append(source.url)

        seen = set()
        unique_urls: list[str] = []
        for url in urls:
            normalized = url.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_urls.append(normalized)
        return unique_urls

    @staticmethod
    def _extract_summary_text(content_blocks) -> str:
        parts = []
        for block in content_blocks:
            text = getattr(block, "text", "")
            if text:
                parts.append(text.strip())
        return "\n\n".join(part for part in parts if part)

    @classmethod
    def _extract_summary_sources(cls, content_blocks) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        seen_urls = set()
        for block in content_blocks:
            for citation in getattr(block, "citations", []) or []:
                if getattr(citation, "type", "") != "web_search_result_location":
                    continue
                url = getattr(citation, "url", "")
                if not url or url in seen_urls:
                    continue
                parsed = urlparse(url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    logger.warning(
                        "Dropping AI summary citation with unsafe URL: %r", url
                    )
                    continue
                seen_urls.add(url)
                title = getattr(citation, "title", "") or cls._display_title_from_url(
                    url
                )
                sources.append({"title": title, "url": url})
        return sources

    @staticmethod
    def _display_title_from_url(url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc or url
