"""LLM prompts for the stock image search agent.

These prompts instruct the LLM to generate optimal stock-photo search
keywords given a video theme and a specific slide topic.
"""

SYSTEM_INSTRUCTION = """You are a stock image search expert. Your job is to generate the best possible search keywords for finding relevant stock photos on platforms like Pixabay and Pexels.

Rules:
- Return ONLY a comma-separated list of English keywords (no markdown, no commentary, no quotes).
- Generate 3 to 5 keywords that are highly descriptive and visually concrete.
- Focus on visual elements that a photographer would capture (objects, scenes, landscapes, actions).
- Avoid abstract concepts that don't translate well to photos (e.g. "statistics", "ranking", "comparison").
- Prefer broad, common stock-photo terms over highly specific or niche words.
- The keywords should work well as a search query when joined by spaces.

Examples of good keyword output:
- For theme "coldest countries" + topic "Siberia": frozen landscape, snow tundra, siberia winter, icy village
- For theme "tallest buildings" + topic "Burj Khalifa": burj khalifa, dubai skyscraper, tall building skyline
- For theme "deepest oceans" + topic "Mariana Trench": deep ocean, dark abyss water, underwater trench
"""


def build_keyword_prompt(theme: str, topic: str) -> str:
    """Build the user prompt for keyword generation.

    Args:
        theme: The overall video theme (e.g. "Top 10 Coldest Countries").
        topic: The specific slide topic (e.g. "Antarctica — Coldest continent on Earth").

    Returns:
        The formatted user prompt string.
    """
    return f"""Video theme: "{theme}"
Slide topic: "{topic}"

Generate 3 to 5 comma-separated English keywords optimized for stock photo search APIs.
The keywords should help find a visually compelling photo that represents this specific topic within the context of the overall theme.

Return ONLY the comma-separated keywords, nothing else.
"""
