"""Image Selector Agent — Pipeline orchestrator."""

import json
import logging
from dataclasses import asdict
from pathlib import Path

from agents.image_selector.image_downloader import download_all_images
from agents.image_selector.gui import ImageSelectorGUI
from agents.image_selector.models import (
    ImageItem,
    ImageSelection,
    SelectorConfig,
    SelectorResult,
    Slide,
)

logger = logging.getLogger(__name__)


class ImageSelectorAgent:
    """Agent that presents images in a slide-based GUI for user selection.

    Pipeline:
        1. Load and parse the input JSON file
        2. Download all images from URLs (cached locally)
        3. Launch the tkinter GUI for user interaction
        4. Collect selections and write the output JSON
    """

    def __init__(self, workspace_dir: Path, output_dir: Path):
        """Initialize the agent.

        Args:
            workspace_dir: Temporary workspace for caching downloaded images.
            output_dir: Default output directory for the selection JSON.
        """
        self._workspace_dir = workspace_dir
        self._output_dir = output_dir
        self._cache_dir = workspace_dir / "image_cache"

        # Ensure directories exist
        self._workspace_dir.mkdir(parents=True, exist_ok=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, config: SelectorConfig) -> SelectorResult:
        """Run the full image selection pipeline.

        Args:
            config: Configuration with input/output paths.

        Returns:
            SelectorResult with selections and skipped slides.
        """
        logger.info(f"{'=' * 60}")
        logger.info("Image Selector Agent")
        logger.info(f"Input: {config.input_path}")
        logger.info(f"Output: {config.output_path}")
        logger.info(f"{'=' * 60}")

        # Step 1: Load input
        logger.info("\n📄 Step 1: Loading input JSON...")
        slides = self._load_input(config.input_path)
        logger.info(f"   Loaded {len(slides)} slides")
        for i, slide in enumerate(slides):
            logger.info(f"   Slide {i + 1}: \"{slide.title}\" ({len(slide.images)} images)")

        # Step 2: Download images
        logger.info("\n📥 Step 2: Downloading images...")
        all_urls = []
        for slide in slides:
            for image in slide.images:
                if image.url and image.url not in all_urls:
                    all_urls.append(image.url)
        logger.info(f"   {len(all_urls)} unique images to download")
        image_paths = download_all_images(all_urls, self._cache_dir)

        # Step 3: Launch GUI
        logger.info("\n🖼️  Step 3: Launching image selector GUI...")
        logger.info("   (Close the window or complete all slides to continue)")
        gui = ImageSelectorGUI(slides, image_paths)
        gui.run()  # Blocks until done

        # Step 4: Write output
        logger.info("\n💾 Step 4: Writing output JSON...")
        result = SelectorResult(
            selections=gui.selections,
            skipped_slides=gui.skipped_slides,
            total_slides=len(slides),
            output_path=config.output_path,
        )
        self._write_output(config.output_path, result)

        logger.info(f"\n{'=' * 60}")
        logger.info("Image selection complete!")
        logger.info(f"   Selections: {len(result.selections)}")
        logger.info(f"   Skipped: {len(result.skipped_slides)}")
        logger.info(f"   Output: {config.output_path}")
        logger.info(f"{'=' * 60}")

        return result

    def _load_input(self, input_path: Path) -> list[Slide]:
        """Step 1: Load and parse the input JSON file into Slide objects."""
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        try:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in input file: {e}") from e

        slides_data = data.get("slides", [])
        if not slides_data:
            raise ValueError("Input JSON must contain a non-empty 'slides' array")

        slides: list[Slide] = []
        for slide_data in slides_data:
            images = [
                ImageItem(
                    description=img.get("description", ""),
                    tags=img.get("tags", []),
                    url=img.get("url", ""),
                )
                for img in slide_data.get("images", [])
            ]
            slides.append(
                Slide(
                    title=slide_data.get("title", "Untitled Slide"),
                    description=slide_data.get("description", ""),
                    images=images,
                )
            )

        return slides

    def _write_output(self, output_path: Path, result: SelectorResult) -> None:
        """Step 4: Write the selection results to a JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_data = {
            "selections": [
                {
                    "slide_index": sel.slide_index,
                    "slide_title": sel.slide_title,
                    "selected_image": {
                        "description": sel.selected_image.description,
                        "tags": sel.selected_image.tags,
                        "url": sel.selected_image.url,
                    },
                }
                for sel in result.selections
            ],
            "skipped_slides": result.skipped_slides,
            "total_slides": result.total_slides,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        logger.info(f"   Output written to: {output_path}")
