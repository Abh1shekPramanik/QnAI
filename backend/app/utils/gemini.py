import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-2.5-flash"


# ── Gemini Call 1: Extract context from transcript (runs every 60s) ──

def extract_context(transcript_text: str) -> dict:
    """Extracts current_subtopic, key_terms, and examples from recent transcript."""
    prompt = f"""
    You are analyzing a live university lecture transcript.
    Extract the following from the transcript below:
    1. current_subtopic — the specific topic currently being discussed (one short phrase)
    2. key_terms — a list of 3-6 important terms or concepts mentioned
    3. examples — a list of any examples or analogies the professor used

    Respond ONLY in this exact JSON format, no markdown, no backticks:
    {{"current_subtopic": "...", "key_terms": ["...", "..."], "examples": ["...", "..."]}}

    If the transcript is empty or unclear, return:
    {{"current_subtopic": "unknown", "key_terms": [], "examples": []}}

    Transcript:
    {transcript_text}
    """
    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = response.text.strip()

    # Parse JSON safely
    import json
    try:
        # Strip markdown fences if model adds them
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        return {"current_subtopic": "unknown", "key_terms": [], "examples": []}


# ── Gemini Call 2: AI brief for confused student (Layer 1) ──

def get_ai_brief(query: str, context: dict, transcript: str = "") -> str:
    """Gives a 2-3 sentence explanation to a confused student."""
    subtopic = context.get("current_subtopic", "the current topic")
    terms = ", ".join(context.get("key_terms", []))
    examples = ", ".join(context.get("examples", []))

    prompt = f"""
    You are a helpful classroom assistant during a live lecture.
    The professor is currently discussing: {subtopic}
    Key terms covered: {terms}
    Examples used: {examples}
    Recent transcript snippet: {transcript[:1000]}

    A student is confused and asks: {query}

    Give a clear, helpful answer in 2-3 sentences. Be direct and simple.
    Do NOT say "based on the transcript" or reference the lecture format.
    """
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text.strip()


# ── Gemini Call 3: Compress question to tag (Layer 2) ──

def compress_query(query: str) -> str:
    """Compresses a student question into a 3-4 word tag."""
    prompt = f"""
    Compress this student question into a 3-4 word tag only.
    No punctuation, no explanation, just the tag.

    Question: {query}
    """
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text.strip()


# ── Gemini Call 4: Categorize tag into a group ──

def categorize_tag(tag: str, existing_categories: list[str] = None) -> str:
    """Assigns a tag to an existing category or creates a new one."""
    cats = ", ".join(existing_categories) if existing_categories else "none yet"

    prompt = f"""
    You are categorizing student confusion tags from a live lecture.
    
    Existing categories: {cats}
    New tag: "{tag}"
    
    Either assign this tag to one of the existing categories, or create a new
    short category name (2-4 words) if none fit.
    
    Respond with ONLY the category name, nothing else.
    """
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text.strip()