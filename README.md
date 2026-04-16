# Kingdom AI Agents

A collection of AI-powered automation agents built with clean architecture principles.

## Architecture

```
kingdom-ai-agents/
├── core/                    # Domain layer (abstractions, no external deps)
│   ├── llm/                 # LLM provider interface
│   └── executor/            # Script executor interface
├── infrastructure/          # Concrete implementations
│   ├── llm/                 # Gemini provider (swappable)
│   └── executor/            # Subprocess executor (swappable)
├── agents/                  # Individual agents
│   └── web_data_exporter/   # First agent: web → JSON
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
   # Edit .env and set your GEMINI_API_KEY
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
