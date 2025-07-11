# nlp_utils.py

import spacy
import re

nlp = spacy.load("en_core_web_sm")

def extract_intent_entities(query: str):
    doc = nlp(query.lower())
    intent = None
    size = None
    vendor = None

    # Intent detection (simple keyword-based)
    if any(word in query for word in ["about", "stock", "size", "details", "info"]):
        intent = "rotor_info"
    elif "pending" in query or "from" in query:
        intent = "vendor_pending"
    elif "vendor" in query and "stock" in query:
        intent = "vendor_stock"

    # Rotor size extraction
    size_match = re.search(r"(\d{2,4})", query)
    if size_match:
        size = int(size_match.group(1))

    # Vendor name (from last ORG/entity or capitalized word after 'from')
    for ent in doc.ents:
        if ent.label_ in ["ORG", "PERSON"]:
            vendor = ent.text.title()

    # If "from XYZ" pattern
    from_match = re.search(r"from\s+([a-zA-Z0-9\s]+)", query)
    if from_match:
        vendor = from_match.group(1).strip().title()

    return {
        "intent": intent,
        "size": size,
        "vendor": vendor
    }
