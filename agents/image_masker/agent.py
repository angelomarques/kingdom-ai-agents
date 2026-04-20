"""Orchestrates terminal strategy selection, download, transform, and save."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from core.ui.terminal_select import SelectConfig, SelectOption, terminal_select

from agents.image_masker.image_downloader import fetch_image_from_url
from agents.image_masker.models import MaskStrategy, MaskerConfig, MaskerResult
from agents.image_masker.transforms import apply_strategies

logger = logging.getLogger(__name__)


def ordered_strategies(selected: set[MaskStrategy]) -> list[MaskStrategy]:
    """Apply order: enum definition order (stable, matches plan table)."""
    return [s for s in MaskStrategy if s in selected]


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

    def run(self, config: MaskerConfig) -> MaskerResult:
        if config.strategies is None:
            strategies = self._prompt_strategies()
        else:
            strategies = list(config.strategies)

        logger.info("Downloading image…")
        img = fetch_image_from_url(config.image_url)

        logger.info("Applying %d strategy/strategies…", len(strategies))
        out_img = apply_strategies(img, strategies)

        if config.output_path is not None:
            out_path = config.output_path
        else:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(config.image_url.encode()).hexdigest()[:12]
            out_path = self._output_dir / f"masked_{digest}.png"

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_img.save(out_path, format="PNG")

        return MaskerResult(
            output_path=out_path,
            applied_strategies=strategies,
            original_url=config.image_url,
        )
