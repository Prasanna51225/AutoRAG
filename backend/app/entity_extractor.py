# backend/app/entity_extractor.py
import re
from collections import defaultdict
from typing import Dict, List, Any
import torch
from transformers import pipeline

# ── BERT NER model ────────────────────────────────────────────────────────────
_DEVICE = 0 if torch.cuda.is_available() else -1
_NER_MODEL = "dslim/bert-base-NER"

_ner_pipeline = None

def _get_ner_pipeline():
    global _ner_pipeline
    if _ner_pipeline is None:
        _ner_pipeline = pipeline(
            "ner",
            model=_NER_MODEL,
            aggregation_strategy="simple",
            device=_DEVICE,
        )
    return _ner_pipeline

# ── Numerical regexes ─────────────────────────────────────────────────────────
_NUM_PATTERNS = {
    "money": re.compile(r'\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|M|B|bn))?', re.IGNORECASE),
    "percentage": re.compile(r'\b\d+(?:\.\d+)?%'),
    "year": re.compile(r'\b(?:19|20)\d{2}\b'),
    "date_full": re.compile(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s*(?:19|20)\d{2}\b', re.IGNORECASE),
    "quantity": re.compile(r'\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:employees|workers|MW|GW|kg|tons?)\b', re.IGNORECASE),
}

# ── Main extractor ────────────────────────────────────────────────────────────

def extract_entities(text: str) -> Dict[str, Any]:
    """
    Returns structured dict with:
      - entities: {PER: [], ORG: [], LOC: [], MISC: []}
      - numerical: {money: [], percentage: [], year: [], date_full: [], quantity: []}
    """
    result = {
        "entities": defaultdict(list),
        "numerical": defaultdict(list),
    }

    # NER
    ner = _get_ner_pipeline()
    # Process in windows to handle long texts
    words = text.split()
    window, step = 400, 350
    seen_entities = defaultdict(set)

    for start in range(0, max(1, len(words) - window + step), step):
        chunk = " ".join(words[start: start + window])
        try:
            for ent in ner(chunk):
                label = ent["entity_group"]  # PER, ORG, LOC, MISC
                word = ent["word"].strip()
                if len(word) >= 2 and word not in seen_entities[label]:
                    seen_entities[label].add(word)
                    result["entities"][label].append(word)
        except Exception:
            pass

    # Convert defaultdict to plain dict
    result["entities"] = dict(result["entities"])

    # Numerical
    for label, pattern in _NUM_PATTERNS.items():
        matches = list(dict.fromkeys(pattern.findall(text)))
        if matches:
            result["numerical"][label] = matches
    result["numerical"] = dict(result["numerical"])

    return result

# ── Query expansion ──────────────────────────────────────────────────────────

def expand_query_with_entities(query: str) -> str:
    # Simple synonym expansion (can be extended)
    expansions = []
    lower_q = query.lower()
    if any(w in lower_q for w in ["ceo", "founder", "director"]):
        expansions.extend(["president", "executive", "head"])
    if any(w in lower_q for w in ["software", "code", "platform"]):
        expansions.extend(["application", "tool", "system"])
    if any(w in lower_q for w in ["location", "city", "country"]):
        expansions.extend(["place", "region", "area"])
    if expansions:
        return f"{query} {' '.join(expansions)}"
    return query