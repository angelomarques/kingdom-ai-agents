# Refactor Reference Research Agent to Use Tavily API

The reference_research agent currently uses **Gemini + Google Search grounding** to find 5 structured-data URLs for a given theme. This refactoring replaces the search/grounding backend with the **Tavily Search API**, which is a dedicated search API that returns URLs, titles, and content snippets directly — without needing an LLM as an intermediary for the search itself.

## User Review Required

> [!IMPORTANT]
> **Architecture decision**: With Tavily, we get search results (URLs + snippets) directly from the API — no LLM is needed for the search step. The current flow uses Gemini to both search (via grounding) _and_ parse/curate the results into JSON. Two approaches:
>
> **Option A – Tavily only (no LLM):** Call Tavily's search, take the top 5 results, and map them directly into `ResearchSource` objects. Simpler, faster, cheaper. The `content_shape` field would be inferred heuristically or set to `"mixed"` by default.
>
> **Option B – Tavily search + LLM curation:** Call Tavily to get ~10 search results, then pass those results to the existing Gemini LLM to curate/rank the best 5 and fill in `content_shape` and `rationale`. More accurate metadata but adds LLM cost and latency.
>
> **I'm proposing Option A** (Tavily-only) for simplicity. Let me know if you'd prefer Option B.

> [!WARNING]
> **Grounding validation removal**: The current agent validates that LLM-suggested URLs are a subset of Google Search grounding evidence URLs. With Tavily, URLs come directly from the search API, so this cross-validation is no longer needed. The `evidence_urls` field on `ResearchResult` will be populated with the same URLs returned by Tavily (or left empty), and the subset check in the agent will be relaxed.

## Proposed Changes

### Infrastructure — New Tavily Research Provider

#### [NEW] [tavily_research.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/infrastructure/research/tavily_research.py)

A new `TavilyResearchProvider` implementing the existing `WebResearchProvider` interface:

- Uses `tavily-python` SDK (`TavilyClient`)
- `find_sources()` calls `client.search(query, max_results=5, search_depth="advanced")`
- Maps Tavily results (`title`, `url`, `content`, `score`) → `ResearchSource` objects
- Sets `content_shape` to `"mixed"` (Tavily doesn't classify page structure)
- Sets `rationale` from the `content` snippet returned by Tavily
- Populates `evidence_urls` with the returned result URLs (for compatibility with the existing model)
- Reads API key from `TAVILY_API_KEY` env var or constructor param

#### [MODIFY] [\_\_init\_\_.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/infrastructure/research/__init__.py)

Export the new `TavilyResearchProvider` alongside the existing Gemini one.

---

### Agent — Update Prompts & Validation

#### [MODIFY] [prompts.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/agents/reference_research/prompts.py)

Remove references to "Google Search grounding" from prompts. Since Option A doesn't use an LLM for the search step, the prompts module becomes largely unused but will be kept for future use (Option B) or removed if you prefer.

#### [MODIFY] [agent.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/agents/reference_research/agent.py)

- Remove the grounding-subset validation in `_validate_sources()` (`require_grounding_subset` logic) since Tavily results are the source of truth
- Simplify `_call_with_optional_retry()`: with Tavily, the retry logic changes — instead of retrying with a broader prompt, we retry with a modified query if < 5 results are returned
- Update error messages to remove "Google Search grounding" references

---

### CLI Wiring

#### [MODIFY] [main.py](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/main.py)

- Update `run_reference_research()` to import and instantiate `TavilyResearchProvider` instead of `GeminiGoogleSearchResearchProvider`
- Update the CLI description to remove Gemini/Google Search references

---

### Dependencies & Configuration

#### [MODIFY] [pyproject.toml](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/pyproject.toml)

Add `tavily-python` to dependencies.

#### [MODIFY] [.env.example](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/.env.example)

Add `TAVILY_API_KEY=your_tavily_api_key_here`.

---

### Documentation

#### [MODIFY] [README.md](file:///home/angelo-marques/projects/personal/kingdom-ai-agents/README.md)

Update the reference-research agent docs to mention Tavily instead of Gemini Google Search grounding.

## Open Questions

1. **Option A vs B** — Do you want Tavily-only (simpler) or Tavily + LLM curation (richer metadata)?
2. **Keep or delete the Gemini research provider?** — Should I keep `gemini_google_search_research.py` for potential future use, or remove it entirely?
3. **`content_shape` field** — With Tavily-only, we can't reliably detect if a page is a "list", "table", or "data" page. Should we default to `"mixed"`, or drop this field?

## Verification Plan

### Automated Tests
- Run `python main.py reference-research --theme "top coldest countries"` to verify end-to-end functionality
- Verify the output JSON has 5 sources with valid https URLs

### Manual Verification
- Inspect output JSON quality and URL relevance
