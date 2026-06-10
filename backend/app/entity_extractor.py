# backend/app/entity_extractor.py
import re
from transformers import pipeline
import torch

# Load NER model (GPU if available)
_device = 0 if torch.cuda.is_available() else -1
ner_pipeline = pipeline("ner", model="dslim/bert-base-NER", device=_device)

def extract_entities(text: str) -> dict:
    """Extract named entities from text."""
    try:
        entities = ner_pipeline(text[:512])  # limit length
        result = {}
        for ent in entities:
            entity_type = ent['entity'].split('-')[-1]  # B-PER -> PER
            word = ent['word']
            if entity_type not in result:
                result[entity_type] = []
            result[entity_type].append(word)
        return result
    except Exception:
        return {}

def expand_query_with_entities(query: str) -> str:
    """Expand query with synonyms for certain entity types."""
    expansions = []
    lower_q = query.lower()
    if any(word in lower_q for word in ["ceo", "founder", "director"]):
        expansions.extend(["president", "executive", "head"])
    if any(word in lower_q for word in ["software", "code", "program"]):
        expansions.extend(["application", "tool", "system"])
    if any(word in lower_q for word in ["location", "city", "country"]):
        expansions.extend(["place", "region", "area"])
    if expansions:
        return f"{query} {' '.join(expansions)}"
    return query