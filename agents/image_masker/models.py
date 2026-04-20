"""Models for the image masker agent."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class MaskStrategy(str, Enum):
    """Available image transforms for content differentiation."""

    HORIZONTAL_FLIP = "horizontal_flip"
    VERTICAL_FLIP = "vertical_flip"
    COLOR_SHIFT = "color_shift"
    ZOOM_CROP = "zoom_crop"
    BORDER_OVERLAY = "border_overlay"
    BRIGHTNESS_CONTRAST = "brightness_contrast"
    SLIGHT_ROTATION = "slight_rotation"
    NOISE_GRAIN = "noise_grain"

    @property
    def title(self) -> str:
        return _STRATEGY_LABELS[self]


_STRATEGY_LABELS: dict[MaskStrategy, str] = {
    MaskStrategy.HORIZONTAL_FLIP: "Horizontal flip — mirror left/right",
    MaskStrategy.VERTICAL_FLIP: "Vertical flip — mirror top/bottom",
    MaskStrategy.COLOR_SHIFT: "Color shift — random hue/saturation",
    MaskStrategy.ZOOM_CROP: "Zoom crop — slight zoom, crop to original size",
    MaskStrategy.BORDER_OVERLAY: "Border overlay — gradient frame around image",
    MaskStrategy.BRIGHTNESS_CONTRAST: "Brightness & contrast — subtle random tweak",
    MaskStrategy.SLIGHT_ROTATION: "Slight rotation — small random angle (2–8°)",
    MaskStrategy.NOISE_GRAIN: "Noise / grain — subtle film grain overlay",
}


@dataclass
class MaskerConfig:
    image_url: str
    output_path: Path | None = None
    # None => interactive terminal picker; set to a list to skip UI (order preserved).
    strategies: list[MaskStrategy] | None = None


@dataclass
class MaskerResult:
    output_path: Path
    applied_strategies: list[MaskStrategy]
    original_url: str
