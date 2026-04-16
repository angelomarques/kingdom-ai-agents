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
│   ├── web_data_exporter/   # Web page → JSON
│   └── json_schema_transformer/  # Raw JSON → Schema-mapped JSON
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
