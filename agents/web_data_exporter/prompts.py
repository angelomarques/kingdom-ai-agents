"""LLM prompts for the Web Data Exporter agent."""

ANALYSIS_SYSTEM_INSTRUCTION = """\
You are an expert web data analyst. Your job is to examine HTML content and \
identify structured data (lists, tables, datasets) that can be exported to JSON.

You focus ONLY on the data — ignore navigation, headers, footers, ads, and \
descriptive paragraphs. Your goal is to identify:
1. What the data is about (the subject)
2. How the data is laid out (HTML table, article sections, lists, etc.)
3. What columns/fields are present

Respond ONLY with valid JSON. No markdown, no code fences, no explanation.
"""


def build_analysis_prompt(html_content: str) -> str:
    """Build the prompt for analyzing HTML structure.

    The LLM should return a JSON object describing the data found.
    """
    # Truncate HTML if too large for context window
    max_chars = 200_000
    if len(html_content) > max_chars:
        html_content = html_content[:max_chars] + "\n<!-- TRUNCATED -->"

    return f"""\
Analyze the following HTML page and identify the primary structured data \
(list/table/dataset) it contains.

Focus on the MAIN DATA CONTENT — ignore navigation, sidebars, footers, and \
meta content. The data might be:
- In an HTML <table> tag
- In article sections where each section describes one item in a list
- In <ul>/<ol> list elements
- In repeated <div> structures

Respond with a JSON object containing:
{{
    "data_layout": "table" | "sections" | "list" | "mixed",
    "subject": "brief description of what the data is about",
    "columns": ["column1", "column2", ...],
    "strategy": "description of how to extract the data",
    "notes": "any important notes about the data structure, edge cases, units, etc."
}}

IMPORTANT:
- Include ALL relevant data columns, including units where applicable \
(e.g., "elevation_meters" instead of just "elevation")
- If data has units, note them in the columns names or in "notes"
- Identify the best CSS selectors or HTML patterns to target

HTML content:
{html_content}
"""


SCRIPT_GENERATION_SYSTEM_INSTRUCTION = """\
You are an expert Python developer specializing in web scraping and data extraction.
You write clean, robust Python scripts using BeautifulSoup to parse HTML files and \
extract structured data into JSON format.

Your scripts must:
1. Read an HTML file from a local path (passed as first command-line argument)
2. Parse it with BeautifulSoup
3. Extract the identified data into a list of dictionaries
4. Write the result as a JSON file (path passed as second command-line argument)
5. Print a summary to stdout (record count, columns found)
6. Handle edge cases gracefully (missing data, inconsistent formatting)

Output ONLY the Python code. No markdown, no code fences, no explanation.
"""


def build_script_generation_prompt(
    html_content: str,
    analysis_subject: str,
    analysis_data_layout: str,
    analysis_columns: list[str],
    analysis_strategy: str,
    analysis_notes: str,
) -> str:
    """Build the prompt for generating the extraction script."""
    # Provide a representative sample of the HTML, not the full thing
    max_chars = 150_000
    if len(html_content) > max_chars:
        html_content = html_content[:max_chars] + "\n<!-- TRUNCATED -->"

    columns_str = ", ".join(f'"{c}"' for c in analysis_columns)

    return f"""\
Write a Python script to extract structured data from the HTML file below.

## Analysis Results
- **Subject**: {analysis_subject}
- **Data layout**: {analysis_data_layout}
- **Expected columns**: [{columns_str}]
- **Extraction strategy**: {analysis_strategy}
- **Notes**: {analysis_notes}

## Requirements
1. The script receives TWO command-line arguments:
   - `sys.argv[1]`: Path to the input HTML file
   - `sys.argv[2]`: Path to the output JSON file
2. Use `BeautifulSoup` with `html.parser` (no lxml dependency needed)
3. Extract data into a list of dictionaries, one dict per record
4. Each dictionary should have these keys: [{columns_str}]
5. Clean up whitespace, remove footnote markers (e.g., [1], [2]), and normalize data
6. For numeric values, try to extract the pure number (remove commas, units inline)
7. But KEEP the unit in a separate field if applicable
8. Write the JSON with `ensure_ascii=False` and `indent=2` for readability
9. Print to stdout: the number of records extracted and the column names
10. Handle missing data by using `null` (None in Python)

## HTML Content (for reference — the script will read it from file)
{html_content}

Write the complete Python script now. Use only standard library + beautifulsoup4.
"""
