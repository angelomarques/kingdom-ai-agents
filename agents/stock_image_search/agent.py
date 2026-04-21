"""Stock image search agent — orchestrates LLM keyword generation + stock image API search."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from core.llm.base import LLMProvider
from core.llm.models import LLMRequest
from core.stock_image.base import StockImageProvider, StockImageProviderError
from core.stock_image.models import StockImage

from agents.stock_image_search.models import StockImageSearchConfig, StockImageSearchResult
from agents.stock_image_search.prompts import SYSTEM_INSTRUCTION, build_keyword_prompt

logger = logging.getLogger(__name__)

_RESULTS_PER_PROVIDER = 5


class StockImageSearchAgent:
    """Orchestrates LLM keyword generation and stock image search across providers.

    Pipeline:
    1. Parse input JSON with theme + slides
    2. For each slide, call the LLM to generate search keywords
    3. Search both Pixabay and Pexels with those keywords (5 results each)
    4. Write a JSON file with all results
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        pixabay_provider: StockImageProvider,
        pexels_provider: StockImageProvider,
        output_dir: Path,
    ):
        self._llm = llm_provider
        self._pixabay = pixabay_provider
        self._pexels = pexels_provider
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, config: StockImageSearchConfig) -> StockImageSearchResult:
        """Execute the full stock image search pipeline.

        Args:
            config: Parsed configuration with theme and slides.

        Returns:
            StockImageSearchResult with the output path and stats.
        """
        logger.info("%s", "=" * 60)
        logger.info("Stock Image Search Agent")
        logger.info("Theme: %s", config.theme)
        logger.info("Slides: %d", len(config.slides))
        logger.info("%s", "=" * 60)

        # Step 1: Generate keywords for each slide via LLM
        slide_keywords = self._generate_all_keywords(config)

        # Step 2: Search both providers for each keyword set
        slide_results = self._search_all_slides(slide_keywords, config)

        # Step 3: Build and write output JSON
        json_path = self._write_output(config, slide_keywords, slide_results)

        images_per_slide = [len(images) for images in slide_results]

        logger.info("Done! Wrote results to %s", json_path)
        return StockImageSearchResult(
            json_path=json_path,
            total_slides=len(config.slides),
            images_per_slide=images_per_slide,
        )

    def _generate_all_keywords(
        self, config: StockImageSearchConfig
    ) -> list[str]:
        """Generate search keywords for each slide using the LLM.

        Returns:
            List of keyword strings, one per slide.
        """
        keywords_list: list[str] = []

        for i, slide in enumerate(config.slides):
            logger.info(
                "[%d/%d] Generating keywords for: %s",
                i + 1, len(config.slides), slide.topic,
            )

            request = LLMRequest(
                prompt=build_keyword_prompt(config.theme, slide.topic),
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.7,
            )

            response = self._llm.generate(request)
            keywords = response.text.strip()

            # Clean up: remove any surrounding quotes or markdown artifacts
            keywords = keywords.strip('"\'`')

            logger.info("  Keywords: %s", keywords)
            keywords_list.append(keywords)

        return keywords_list

    def _search_all_slides(
        self,
        slide_keywords: list[str],
        config: StockImageSearchConfig,
    ) -> list[list[StockImage]]:
        """Search Pixabay and Pexels for each slide's keywords.

        Returns:
            List of image lists, one per slide. Each inner list has
            up to 10 images (5 from Pixabay + 5 from Pexels).
        """
        all_results: list[list[StockImage]] = []

        for i, keywords in enumerate(slide_keywords):
            topic = config.slides[i].topic
            logger.info(
                "[%d/%d] Searching images for: %s",
                i + 1, len(slide_keywords), topic,
            )

            slide_images: list[StockImage] = []

            # Search Pixabay
            try:
                pixabay_results = self._pixabay.search(
                    query=keywords, per_page=_RESULTS_PER_PROVIDER
                )
                slide_images.extend(pixabay_results)
                logger.info("  Pixabay: %d results", len(pixabay_results))
            except StockImageProviderError as e:
                logger.warning("  Pixabay search failed: %s", e)

            # Search Pexels
            try:
                pexels_results = self._pexels.search(
                    query=keywords, per_page=_RESULTS_PER_PROVIDER
                )
                slide_images.extend(pexels_results)
                logger.info("  Pexels: %d results", len(pexels_results))
            except StockImageProviderError as e:
                logger.warning("  Pexels search failed: %s", e)

            all_results.append(slide_images)

        return all_results

    def _write_output(
        self,
        config: StockImageSearchConfig,
        slide_keywords: list[str],
        slide_results: list[list[StockImage]],
    ) -> Path:
        """Build the output JSON and write it to disk.

        Returns:
            Path to the written JSON file.
        """
        slides_output = []
        for i, slide in enumerate(config.slides):
            slides_output.append({
                "topic": slide.topic,
                "keywords": slide_keywords[i],
                "images": [img.to_dict() for img in slide_results[i]],
            })

        payload = {
            "theme": config.theme,
            "slides": slides_output,
        }

        if config.output_path is not None:
            json_path = config.output_path.expanduser().resolve()
            json_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            json_path = (self._output_dir / config.derive_output_basename()).resolve()

        json_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info("Wrote %s", json_path)
        return json_path
