import json, os, re, httpx

def retrieve(text, brand, k=5):
    """Minimal RAG: rank Brand DNA lines by word overlap with the content."""
    words = set(re.findall(r"\w{4,}", text.lower()))
    pool = [l for f in ("communication_guidelines", "verified_facts", "approved_claims") for l in (brand.get(f) or "").splitlines() if l.strip()]
    return sorted(pool, key=lambda l: -len(words & set(re.findall(r"\w{4,}", l.lower()))))[:k]

def gemini_findings(text, brand, context):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return [], "Gemini not configured: deterministic rules only (demo mode)."
    prompt = ("You are a brand compliance reviewer. Using ONLY these approved rules and facts, find tone, factual-conflict or unsupported-claim problems. "
              "Do not call a claim false just because it is missing; label it unsupported. Return a JSON array of objects with keys "
              "flagged_text, category, severity (High/Medium/Low), brand_rule, explanation, suggested_correction, evidence.\n"
              f"Brand: {brand.get('brand_name')} | Tone: {brand.get('tone')}\nRules/facts:\n" + "\n".join(context) + f"\n\nContent:\n{text}")
    try:
        r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('GEMINI_MODEL','gemini-2.0-flash')}:generateContent",
                       headers={"x-goog-api-key": key}, timeout=30,
                       json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}})
        r.raise_for_status()
        items = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        return [{**i, "source": "gemini"} for i in items if isinstance(i, dict) and i.get("flagged_text")], "Gemini analysis included."
    except Exception as e:
        return [], f"Gemini call failed ({type(e).__name__}); rules-only results shown."
