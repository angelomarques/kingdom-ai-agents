"""LLM prompts for the JSON Schema Transformer agent."""

ANALYSIS_SYSTEM_INSTRUCTION = """\
You are an expert data transformation analyst. Your job is to examine a raw \
JSON data file and a target JSON schema, then determine exactly how each \
field in the target schema should be derived from the raw data.

You must identify:
1. Direct field mappings (rename / copy)
2. Computed fields (concatenations, formatting, math, etc.)
3. Sorting requirements specified in the schema descriptions
4. Type conversions (string → number, date formatting, etc.)
5. Any edge cases or ambiguities

Respond ONLY with valid JSON. No markdown, no code fences, no explanation.\
"""


def build_analysis_prompt(raw_data_content: str, schema_content: str) -> str:
    """Build the prompt for analyzing the transformation requirements.

    The LLM should return a JSON object describing every field mapping.
    """
    # Truncate if too large for context window
    max_chars = 200_000
    if len(raw_data_content) > max_chars:
        raw_data_content = raw_data_content[:max_chars] + "\n<!-- TRUNCATED -->"

    return f"""\
Analyze the following raw JSON data and target schema. Determine how each \
property in the target schema should be produced from the raw data.

Pay close attention to the "description" field of each schema property — it \
often specifies the transformation rule (e.g., "Concatenation of field_a and \
field_b", "Formatted as YYYY-MM-DD", "Sorted by name ascending").

Also look at the top-level schema description for sorting instructions.

Respond with a JSON object containing:
{{
    "field_mappings": [
        {{
            "target_field": "name of the output property",
            "source_fields": ["raw_field_1", "raw_field_2"],
            "transformation": "rename" | "concatenate" | "format" | "compute" | "copy" | "constant" | "conditional",
            "description": "Human-readable explanation of how to produce this field"
        }}
    ],
    "sorting": "Sorting instructions if any, otherwise empty string",
    "notes": "Any additional observations, edge cases, or ambiguities"
}}

IMPORTANT:
- Map EVERY property in the target schema — do not skip any.
- If a field has no obvious source, flag it in notes.
- Be specific about string concatenation separators, date formats, etc.
- Include any filtering or deduplication if mentioned in the schema.

## Raw Data (raw-data.json)
{raw_data_content}

## Target Schema (schema.json)
{schema_content}
"""


SCRIPT_GENERATION_SYSTEM_INSTRUCTION = """\
You are an expert Python developer specializing in data transformation. \
You write clean, robust Python scripts that transform JSON data from one \
structure to another based on a schema and explicit mapping rules.

Your scripts must:
1. Read raw-data.json from a local path (passed as first command-line argument)
2. Read schema.json from a local path (passed as second command-line argument)
3. Transform the data according to the analysis and schema
4. Write the result as a JSON file (path passed as third command-line argument)
5. Print a summary to stdout (record count, columns found)
6. Handle edge cases gracefully (missing fields, null values, type mismatches)

Output ONLY the Python code. No markdown, no code fences, no explanation.\
"""


def build_script_generation_prompt(
    raw_data_content: str,
    schema_content: str,
    analysis_field_mappings: list[dict],
    analysis_sorting: str,
    analysis_notes: str,
) -> str:
    """Build the prompt for generating the transformation script."""
    import json

    # Truncate if too large
    max_chars = 150_000
    if len(raw_data_content) > max_chars:
        raw_data_content = raw_data_content[:max_chars] + "\n<!-- TRUNCATED -->"

    mappings_str = json.dumps(analysis_field_mappings, indent=2, ensure_ascii=False)

    return f"""\
Write a Python script to transform raw JSON data into a new JSON file \
following the target schema.

## Analysis Results
- **Field mappings**:
{mappings_str}

- **Sorting**: {analysis_sorting if analysis_sorting else "None specified"}
- **Notes**: {analysis_notes if analysis_notes else "None"}

## Requirements
1. The script receives THREE command-line arguments:
   - `sys.argv[1]`: Path to the input raw-data.json file
   - `sys.argv[2]`: Path to the schema.json file
   - `sys.argv[3]`: Path to the output JSON file
2. Use ONLY the Python standard library (json, sys, re, etc.) — no external packages
3. Read raw-data.json and transform each record according to the field mappings
4. Apply any sorting specified in the analysis
5. The output should be a JSON array of objects matching the target schema
6. Write the JSON with `ensure_ascii=False` and `indent=2` for readability
7. Print to stdout: the number of records transformed and the output column names
8. Handle missing data by using `null` (None in Python)
9. Handle type conversions as specified (string to number, etc.)
10. For concatenation fields, use exactly the separator described in the schema

## Raw Data (raw-data.json — for reference, the script reads it from file)
{raw_data_content}

## Target Schema (schema.json — for reference, the script reads it from file)
{schema_content}

Write the complete Python script now. Use only the standard library.
"""
