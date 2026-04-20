"""Pillow-based masking transforms (no LLM)."""

from __future__ import annotations

import random
from collections.abc import Callable

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from agents.image_masker.models import MaskStrategy


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "RGB":
        return img
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    return img.convert("RGB")


def apply_horizontal_flip(img: Image.Image) -> Image.Image:
    return ImageOps.mirror(_to_rgb(img))


def apply_vertical_flip(img: Image.Image) -> Image.Image:
    return ImageOps.flip(_to_rgb(img))


def apply_color_shift(img: Image.Image) -> Image.Image:
    im = _to_rgb(img).convert("HSV")
    h_ch, s_ch, v_ch = im.split()
    h_arr = np.array(h_ch, dtype=np.int16)
    s_arr = np.array(s_ch, dtype=np.float32)
    dh = random.randint(-40, 40)
    h_arr = (h_arr + dh) % 256
    ds = random.uniform(0.88, 1.12)
    s_arr = np.clip(s_arr * ds, 0, 255).astype(np.uint8)
    out = Image.merge(
        "HSV",
        (
            Image.fromarray(h_arr.astype(np.uint8), mode="L"),
            Image.fromarray(s_arr, mode="L"),
            v_ch,
        ),
    )
    return out.convert("RGB")


def apply_zoom_crop(img: Image.Image) -> Image.Image:
    img = _to_rgb(img)
    w, h = img.size
    scale = random.uniform(1.05, 1.12)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return resized.crop((left, top, left + w, top + h))


def apply_border_overlay(img: Image.Image) -> Image.Image:
    img = _to_rgb(img)
    w, h = img.size
    border = max(6, min(w, h) // 25)
    nw, nh = w + 2 * border, h + 2 * border
    c1 = np.random.randint(30, 220, size=3).astype(np.float32)
    c2 = np.random.randint(30, 220, size=3).astype(np.float32)
    yy, xx = np.mgrid[0:nh, 0:nw].astype(np.float32)
    t = (xx / max(nw - 1, 1) + yy / max(nh - 1, 1)) / 2.0
    t3 = np.stack([t, t, t], axis=-1)
    pixels = c1 * (1.0 - t3) + c2 * t3
    canvas = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), mode="RGB")
    canvas.paste(img, (border, border))
    return canvas


def apply_brightness_contrast(img: Image.Image) -> Image.Image:
    img = _to_rgb(img)
    b = ImageEnhance.Brightness(img).enhance(random.uniform(0.9, 1.12))
    return ImageEnhance.Contrast(b).enhance(random.uniform(0.92, 1.12))


def apply_slight_rotation(img: Image.Image) -> Image.Image:
    img = _to_rgb(img)
    w, h = img.size
    angle = random.uniform(2.0, 8.0) * (1.0 if random.random() < 0.5 else -1.0)
    rotated = img.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(255, 255, 255),
    )
    rw, rh = rotated.size
    left = (rw - w) // 2
    top = (rh - h) // 2
    return rotated.crop((left, top, left + w, top + h))


def apply_noise_grain(img: Image.Image) -> Image.Image:
    img = _to_rgb(img)
    arr = np.array(img, dtype=np.float32)
    sigma = random.uniform(3.0, 10.0)
    noise = np.random.randn(*arr.shape).astype(np.float32) * sigma
    out = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(out, mode="RGB")


STRATEGY_MAP: dict[MaskStrategy, Callable[[Image.Image], Image.Image]] = {
    MaskStrategy.HORIZONTAL_FLIP: apply_horizontal_flip,
    MaskStrategy.VERTICAL_FLIP: apply_vertical_flip,
    MaskStrategy.COLOR_SHIFT: apply_color_shift,
    MaskStrategy.ZOOM_CROP: apply_zoom_crop,
    MaskStrategy.BORDER_OVERLAY: apply_border_overlay,
    MaskStrategy.BRIGHTNESS_CONTRAST: apply_brightness_contrast,
    MaskStrategy.SLIGHT_ROTATION: apply_slight_rotation,
    MaskStrategy.NOISE_GRAIN: apply_noise_grain,
}


def apply_strategies(img: Image.Image, strategies: list[MaskStrategy]) -> Image.Image:
    """Apply transforms in list order; returns RGB."""
    out = _to_rgb(img)
    for s in strategies:
        out = STRATEGY_MAP[s](out)
        if out.mode != "RGB":
            out = out.convert("RGB")
    return out
