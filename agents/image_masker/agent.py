"""Orchestrates terminal strategy selection, download, transform, and save."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from core.ui.terminal_select import SelectConfig, SelectOption, terminal_select

from agents.image_masker.image_downloader import fetch_image_from_url, load_image_from_path
from agents.image_masker.models import (
    SUPPORTED_IMAGE_EXTENSIONS,
    MaskStrategy,
    MaskerBatchResult,
    MaskerConfig,
    MaskerResult,
)
from agents.image_masker.transforms import apply_strategies

logger = logging.getLogger(__name__)


def ordered_strategies(selected: set[MaskStrategy]) -> list[MaskStrategy]:
    """Apply order: enum definition order (stable, matches plan table)."""
    return [s for s in MaskStrategy if s in selected]


def list_images_in_dir(input_dir: Path) -> list[Path]:
    """Return supported image files in a directory, sorted by name."""
    images = [
        path
        for path in input_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        and not path.stem.startswith("masked_")
    ]
    return sorted(images, key=lambda p: p.name.lower())


class ImageMaskerAgent:
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def _prompt_strategies(self) -> list[MaskStrategy]:
        options = [SelectOption(label=s.title, value=s, selected=False) for s in MaskStrategy]
        config = SelectConfig(
            title="Masking strategies (↑/↓ navigate, Space/Enter toggle, d done, q cancel):",
            multi_select=True,
        )
        result = terminal_select(options, config)
        chosen = {o.value for o in result if o.selected}
        return ordered_strategies(chosen)

    def _resolve_strategies(self, config: MaskerConfig) -> list[MaskStrategy]:
        if config.strategies is None:
            return self._prompt_strategies()
        return list(config.strategies)

    def _output_path_for_url(self, image_url: str, output_path: Path | None) -> Path:
        if output_path is not None:
            return output_path
        self._output_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(image_url.encode()).hexdigest()[:12]
        return self._output_dir / f"masked_{digest}.png"

    def _output_path_for_file(
        self,
        input_path: Path,
        output_dir: Path,
    ) -> Path:
        return output_dir / f"masked_{input_path.stem}.png"

    def _mask_and_save(
        self,
        img,
        strategies: list[MaskStrategy],
        out_path: Path,
        source: str,
    ) -> MaskerResult:
        out_img = apply_strategies(img, strategies)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_img.save(out_path, format="PNG")
        return MaskerResult(
            output_path=out_path,
            applied_strategies=strategies,
            source=source,
        )

    def _run_single(self, config: MaskerConfig, strategies: list[MaskStrategy]) -> MaskerResult:
        assert config.image_url is not None

        logger.info("Downloading image…")
        img = fetch_image_from_url(config.image_url)

        logger.info("Applying %d strategy/strategies…", len(strategies))
        out_path = self._output_path_for_url(config.image_url, config.output_path)
        return self._mask_and_save(img, strategies, out_path, config.image_url)

    def _run_batch(self, config: MaskerConfig, strategies: list[MaskStrategy]) -> MaskerBatchResult:
        assert config.input_dir is not None

        image_paths = list_images_in_dir(config.input_dir)
        if not image_paths:
            raise ValueError(
                f"No supported images found in: {config.input_dir} "
                f"(extensions: {', '.join(sorted(SUPPORTED_IMAGE_EXTENSIONS))})"
            )

        output_dir = config.output_path if config.output_path is not None else self._output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        results: list[MaskerResult] = []
        total = len(image_paths)
        for index, input_path in enumerate(image_paths, start=1):
            logger.info("Processing image %d/%d: %s", index, total, input_path.name)
            img = load_image_from_path(input_path)
            out_path = self._output_path_for_file(input_path, output_dir)
            results.append(
                self._mask_and_save(
                    img,
                    strategies,
                    out_path,
                    str(input_path.resolve()),
                )
            )

        return MaskerBatchResult(
            results=results,
            applied_strategies=strategies,
            input_dir=config.input_dir,
        )

    def run(self, config: MaskerConfig) -> MaskerResult | MaskerBatchResult:
        strategies = self._resolve_strategies(config)

        if config.input_dir is not None:
            return self._run_batch(config, strategies)
        return self._run_single(config, strategies)
