# Image Masker Agent

Build a new agent that takes an image URL, lets the user pick which masking strategies to apply via an interactive terminal multi-select, then applies those transforms using Pillow and saves the result.

## User Review Required

> [!IMPORTANT]
> **Masking strategies** — I've compiled 8 common techniques used to alter images to avoid content-matching systems. Please review the list and let me know if you'd like to add/remove any.

> [!IMPORTANT]
> **Reusable terminal select** — This will be built as a core module at `core/ui/terminal_select.py` using raw terminal input (no external TUI library). It will support both single-select and multi-select modes so other agents can reuse it.

## Proposed Changes

### Core UI Module — Reusable Terminal Select

A new `core/ui/` package providing a generic, reusable interactive select component for the terminal.

#### [NEW] [__init__.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/core/ui/__init__.py)

Package init exporting the public API.

#### [NEW] [terminal_select.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/core/ui/terminal_select.py)

The core reusable select logic:

- **`SelectOption`** dataclass — holds `label: str`, `value: Any`, `selected: bool`
- **`SelectConfig`** dataclass — holds `title: str`, `multi_select: bool`, `highlight_color: str` (ANSI color code)
- **`TerminalSelect`** class with:
  - Raw terminal mode via `tty`/`termios` (stdlib, no deps)
  - Arrow key navigation (↑/↓) with cursor wrapping
  - **Enter** to toggle selection (multi-select) or confirm (single-select)
  - **Space** to toggle in multi-select mode
  - **`q`** or **Ctrl+C** to cancel
  - **`d`** (done) to confirm multi-select choices
  - Active line highlighted with color (e.g., cyan background), selected items shown with `[✓]` / unselected with `[ ]`
  - Full screen clearing and re-rendering on each keystroke
- **`terminal_select(options, config)`** — convenience function that creates a `TerminalSelect` and runs it, returning `list[SelectOption]`

---

### Image Masker Agent

#### [NEW] [__init__.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/agents/image_masker/__init__.py)

Package init.

#### [NEW] [models.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/agents/image_masker/models.py)

Data models:

- **`MaskStrategy`** enum — the 8 available transforms:
  | Strategy | Description |
  |---|---|
  | `HORIZONTAL_FLIP` | Mirror the image horizontally |
  | `VERTICAL_FLIP` | Mirror the image vertically |
  | `COLOR_SHIFT` | Shift hue/saturation by a random amount |
  | `ZOOM_CROP` | Zoom in slightly and crop to original dimensions |
  | `BORDER_OVERLAY` | Add a colored/gradient border around the image |
  | `BRIGHTNESS_CONTRAST` | Randomly adjust brightness and contrast |
  | `SLIGHT_ROTATION` | Rotate by a small random angle (2–8°) |
  | `NOISE_GRAIN` | Overlay subtle noise / film grain |

- **`MaskerConfig`** — `image_url: str`, `output_path: Path | None`, `strategies: list[MaskStrategy]`
- **`MaskerResult`** — `output_path: Path`, `applied_strategies: list[MaskStrategy]`, `original_url: str`

#### [NEW] [transforms.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/agents/image_masker/transforms.py)

Pure image-processing functions (Pillow-based, no LLM):

- `apply_horizontal_flip(img: Image) -> Image`
- `apply_vertical_flip(img: Image) -> Image`
- `apply_color_shift(img: Image) -> Image`
- `apply_zoom_crop(img: Image) -> Image`
- `apply_border_overlay(img: Image) -> Image`
- `apply_brightness_contrast(img: Image) -> Image`
- `apply_slight_rotation(img: Image) -> Image`
- `apply_noise_grain(img: Image) -> Image`
- `STRATEGY_MAP: dict[MaskStrategy, Callable]` — maps enum → function
- `apply_strategies(img: Image, strategies: list[MaskStrategy]) -> Image` — applies all selected transforms in order

#### [NEW] [image_downloader.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/agents/image_masker/image_downloader.py)

Simple function to download an image from a URL and return a Pillow `Image` object. Reuses the same `httpx` pattern from the existing `image_selector` agent.

#### [NEW] [agent.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/agents/image_masker/agent.py)

Pipeline orchestrator:

1. **Present terminal multi-select** — show all 8 strategies, user picks which ones to apply
2. **Download the image** from the provided URL
3. **Apply selected transforms** in sequence
4. **Save the result** to the output path
5. Return `MaskerResult`

---

### CLI Integration

#### [MODIFY] [main.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/main.py)

Add a new `image-mask` subcommand:

```
python main.py image-mask --url "https://example.com/photo.jpg"
python main.py image-mask --url "https://example.com/photo.jpg" --output "masked_photo.png"
```

#### [MODIFY] [README.md](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/README.md)

Add documentation for:
- The new Image Masker agent (usage, strategies)
- The architecture tree update

---

### Dependencies

#### [MODIFY] [pyproject.toml](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/pyproject.toml)

Add `numpy` for noise grain generation. All other transforms use only Pillow (already installed).

## Open Questions

1. **Strategy list** — Are these 8 transforms the ones you want? Want to add/remove any?
2. **Output format** — Should the output default to PNG (lossless) or match the original format?
3. **Strategy ordering** — Should the transforms be applied in the order shown above (flip → color → zoom → border → brightness → rotation → noise) or in the order the user selects them?

## Verification Plan

### Automated Tests
- Run `uv run python main.py image-mask --help` to verify CLI registration
- Run the agent with a public-domain test image URL to verify the full pipeline end-to-end

### Manual Verification
- Visually confirm the terminal multi-select renders correctly with arrow key navigation and color highlighting
- Visually confirm the output image has the expected transforms applied
