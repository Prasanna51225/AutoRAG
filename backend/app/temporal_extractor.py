# backend/app/temporal_extractor.py
import re
from dateutil import parser

def extract_dates(text: str) -> list:
    """Extract dates (years and full dates) from text."""
    years = re.findall(r'\b(19|20)\d{2}\b', text)
    dates = re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', text)
    parsed = []
    for d in dates:
        try:
            parsed.append(parser.parse(d).isoformat())
        except:
            pass
    all_dates = list(set(years + parsed))
    return all_dates