"""LLM prompts for the reference research agent.

These prompts are used by the agent layer when the research provider needs
retry guidance. The main curation prompt lives inside the infrastructure
provider (TavilyResearchProvider) since it's tightly coupled to the search
result format.
"""

SYSTEM_INSTRUCTION = """You are a research assistant helping creators make videos or articles that rely on structured facts: ranked lists, comparisons, tables, or bullet-point data.

Rules:
- Return ONLY valid JSON (no markdown fences, no commentary).
- Suggest exactly five distinct https URLs.
- Prefer pages that visibly present facts as a numbered/bulleted list, table, dataset, or clearly scannable sections (not long prose essays without structure).
- Prefer reputable sources (government statistics, Wikipedia data pages, major encyclopedias, established news data desks, university references) when possible.
- Each URL must be a real page found via web search; do not invent URLs.
- The JSON shape must be:
  {"sources":[{"url":"...","title":"...","content_shape":"list|table|data|mixed","rationale":"..."}]}
- content_shape: use "table" if the main facts are in a table; "list" for ranked/bulleted lists; "data" for numeric/stat blocks or downloadable-style figures; "mixed" if both prose and structured blocks appear.
"""


def build_user_prompt(theme: str) -> str:
    return f"""Theme / topic for the creator's content:

"{theme}"

Task: pick exactly 5 web pages someone could use as primary fact references for this theme. Each page should make it easy to extract or read off structured facts (lists, tables, rankings, comparisons).

Return JSON only, with this exact structure:
{{"sources":[{{"url":"https://...","title":"...","content_shape":"list|table|data|mixed","rationale":"..."}}, ...]}}

There must be exactly 5 objects in "sources", and all URLs must use https.
"""


def build_retry_user_prompt(theme: str) -> str:
    return f"""The previous attempt did not return enough distinct web sources.

Theme (unchanged): "{theme}"

Please use broader queries (synonyms, related rankings, "list of", statistics bureaus, Wikipedia list pages, etc.) and return again ONLY valid JSON with exactly 5 distinct https URLs in:

{{"sources":[{{"url":"https://...","title":"...","content_shape":"list|table|data|mixed","rationale":"..."}}, ...]}}

Requirements:
- Exactly 5 items in "sources"
- Each URL must come from real web pages
- Prefer structured presentations: tables, bullet lists, ranked lists, comparison charts, numeric datasets
"""
