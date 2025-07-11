# nlp_utils.py

import spacy
import re

nlp = spacy.load("en_core_web_sm")
def extract_intent_entities(query: str):
    doc = nlp(query.lower())
    intent = None
    size = None
    vendor = None
    entry_index = None

    if "edit" in query or "update" in query:
        intent = "edit_entry"

    size_match = re.search(r"(\d{2,4})", query)
    if size_match:
        size = int(size_match.group(1))

    from_match = re.search(r"from\s+([a-zA-Z0-9\s]+)", query)
    if from_match:
        vendor = from_match.group(1).strip().title()

    idx_match = re.search(r"entry\s*(\d+)", query)
    if idx_match:
        entry_index = int(idx_match.group(1)) - 1  # human-friendly (1-based)

    return {
        "intent": intent,
        "size": size,
        "vendor": vendor,
        "index": entry_index
    }
