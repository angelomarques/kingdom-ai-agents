# Kingdom AI Agents

A collection of AI-powered automation agents built with clean architecture principles.

## Architecture

```
kingdom-ai-agents/
├── core/                    # Domain layer (abstractions, no external deps)
│   ├── llm/                 # LLM provider interface
│   ├── research/            # Web research port (URL discovery)
│   ├── ui/                  # Reusable terminal UI (e.g. raw-mode select)
│   └── executor/            # Script executor interface
├── infrastructure/          # Concrete implementations
│   ├── llm/                 # Gemini provider (swappable)
│   ├── research/            # Tavily Search + LLM curation
│   └── executor/            # Subprocess executor (swappable)
├── agents/                  # Individual agents
│   ├── web_data_exporter/   # Web page → JSON
│   ├── json_schema_transformer/  # Raw JSON → Schema-mapped JSON
│   ├── reference_research/  # Theme → five grounded reference URLs (JSON)
│   ├── image_selector/      # Slide-based image selection GUI
│   └── image_masker/        # URL image → terminal-picked Pillow transforms → PNG
├── workspace/               # Temp files (HTML downloads, generated scripts)
└── output/                  # Final JSON output files
```

## Setup

1. **Install dependencies** (requires [uv](https://docs.astral.sh/uv/)):
   ```bash
   uv sync
   ```

2. **Configure API key**:
   ```bash
   cp .env.example .env
   # Edit .env and set your GEMINI_API_KEY and TAVILY_API_KEY
   ```

## Agents

### Web Data Exporter

Exports structured list/table data from web pages to JSON files.

**How it works:**
1. Downloads the HTML page
2. Uses Gemini to analyze the page structure (tables, article sections, lists)
3. Uses Gemini to generate a Python extraction script
4. Runs the script via subprocess to extract the data
5. Saves the structured JSON output

**Usage:**
```bash
# Basic usage (output filename auto-derived from URL)
uv run python main.py web-export --url "https://en.wikipedia.org/wiki/List_of_capital_cities_by_elevation"

# With custom output filename
uv run python main.py web-export --url "https://en.wikipedia.org/wiki/List_of_capital_cities_by_elevation" --output "capitals_elevation.json"

# Verbose mode (debug logging)
uv run python main.py web-export -v --url "https://example.com/data-page"
```

### Reference Research

Finds five **https** pages you can use as primary references for fact-heavy content (ranked lists, comparisons, tables, bullet-point data). Uses the **[Tavily Search API](https://tavily.com)** to discover candidate pages and a **Gemini LLM** to curate the best five results with structured metadata.

**How it works:**
1. Sends the theme to Tavily Search API (advanced depth, up to 10 results)
2. If fewer than 5 results are found, retries with a broader query (synonyms, related terms)
3. Passes all search results to an LLM to curate the best 5 pages
4. The LLM picks 5 URLs from the search results and fills in `content_shape` and `rationale`
5. Validates five distinct **https** URLs and checks each curated URL appears in the Tavily results
6. Writes `theme` + `sources` to a JSON file under `output/` (or `--output`)

**Notes:** Requires both `TAVILY_API_KEY` and `GEMINI_API_KEY` environment variables. Tavily usage follows its API billing policies.

**Usage:**
```bash
uv run python main.py reference-research --theme "top coldest countries"

# Custom output path
uv run python main.py reference-research --theme "curious facts about the sea" --output ./output/sea_facts_refs.json

uv run python main.py reference-research -v --theme "tallest buildings in europe"
```

### JSON Schema Transformer

Transforms raw JSON data into a new JSON structure based on a target schema.

**How it works:**
1. Reads `raw-data.json` and `schema.json` from the input directory
2. Uses Gemini to analyze the transformation requirements (field mappings, concatenations, sorting, etc.)
3. Uses Gemini to generate a Python transformation script
4. Runs the script via subprocess to transform the data
5. Saves the structured JSON output as `output.json` in the same directory

The agent is able to identify patterns in each property. For example, if a property is the union of two fields resulting in a concatenated string, specify this in the property `description` in the schema.

**Input files:**
- `raw-data.json` — The source data (array of objects)
- `schema.json` — The target schema with property descriptions explaining the transformation rules

**Usage:**
```bash
# Basic usage
uv run python main.py json-transform --input-dir "./my-data-folder"

# Verbose mode (debug logging)
uv run python main.py json-transform -v --input-dir "./my-data-folder"
```

### Image Selector

Presents images in a slide-based GUI for manual selection. No LLM required.

**How it works:**
1. Reads a JSON file containing slides, each with a list of images (URL, description, tags)
2. Downloads all images from URLs (cached locally in `workspace/image_cache/`)
3. Launches a tkinter GUI where the user selects one image per slide (or skips)
4. Saves the selections to a JSON output file

**Input JSON format:**
```json
{
  "slides": [
    {
      "title": "Choose a background",
      "description": "Select the best landscape photo",
      "images": [
        {
          "description": "A sunset over mountains",
          "tags": ["sunset", "mountains"],
          "url": "https://example.com/image1.jpg"
        }
      ]
    }
  ]
}
```

**Usage:**
```bash
# Basic usage (output defaults to output/selections.json)
uv run python main.py image-select --input "./slides.json"

# With custom output path
uv run python main.py image-select --input "./slides.json" --output "./my_selections.json"

# Verbose mode
uv run python main.py image-select -v --input "./slides.json"
```

### Image Masker

Downloads an image from a URL, lets you pick which masking strategies to apply in an interactive terminal multi-select (arrow keys, Space/Enter to toggle, `d` when done, `q` to cancel), then applies the transforms with Pillow and NumPy and saves a **PNG** (lossless default).

**Strategies (stable apply order follows this list):**

| Strategy | Effect |
|----------|--------|
| `horizontal_flip` | Mirror left/right |
| `vertical_flip` | Mirror top/bottom |
| `color_shift` | Random hue/saturation shift (HSV) |
| `zoom_crop` | Slight zoom then center crop to original size |
| `border_overlay` | Gradient-colored border around the image |
| `brightness_contrast` | Random subtle brightness and contrast |
| `slight_rotation` | Small random rotation (about 2–8°), cropped square |
| `noise_grain` | Subtle Gaussian noise / grain |

**Usage:**

```bash
# Output path defaults to output/masked_<hash>.png
uv run python main.py image-mask --url "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png"

# Custom output path
uv run python main.py image-mask --url "https://example.com/photo.jpg" --output "./masked_photo.png"

uv run python main.py image-mask -v --url "https://example.com/photo.jpg"
```

For programmatic runs without a TTY, construct `MaskerConfig(..., strategies=[...])` and call `ImageMaskerAgent(...).run(config)` so the terminal picker is skipped.

**Example schema.json:**
```json
{
  "description": "Sorted by full_name ascending",
  "properties": {
    "full_name": {
      "type": "string",
      "description": "Concatenation of first_name and last_name separated by a space"
    },
    "age": {
      "type": "number",
      "description": "Direct mapping from the age field"
    }
  }
}
```

## Adding a New LLM Provider

Implement `core.llm.base.LLMProvider`:

```python
class MyProvider(LLMProvider):
    def generate(self, request: LLMRequest) -> LLMResponse:
        ...

    @property
    def default_model(self) -> str:
        return "my-model"
```

Then wire it up in `main.py` instead of `GeminiProvider`.

## Adding a New Agent

1. Create a folder under `agents/your_agent_name/`
2. Add a subcommand in `main.py`'s `build_parser()` function
3. Follow the same pattern as `web_data_exporter`
