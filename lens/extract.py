"""CoA extraction: turn a certificate of analysis into structured fields.

Two routes, same output shape:
- a deterministic parser for labelled CoA text (the bundled fixtures,
  and any CoA that states its fields plainly), and
- a language-model call for messier documents, used only when an API
  key is configured in Streamlit Secrets.

Either way, the extracted values are checked by lens.core — the model
proposes values; Python disposes.
"""
from __future__ import annotations

import json
import re
import urllib.request

LABS = ["Pacific BioTest", "Meridian Analytical", "ClearLine Labs"]

TEST_KEYS = [
    ("endotoxin", "Bacterial Endotoxins"),
    ("bioburden", "Bioburden"),
    ("toc", "Total Organic Carbon"),
    ("sterility", "Sterility"),
]


def _line(pattern, text):
    m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    return m.group(0).strip() if m else ""


def parse_coa_text(text):
    """Deterministic extraction from a labelled CoA. Returns a dict;
    fields that are absent come back as None, never invented."""
    out = {"evidence": {}}

    m = re.search(r"Sample ID:\s*(\S+)", text, flags=re.IGNORECASE)
    out["sample_id"] = m.group(1) if m else None
    if m:
        out["evidence"]["sample_id"] = _line(r"Sample ID:.*", text)

    m = re.search(r"Test:\s*(.+)", text, flags=re.IGNORECASE)
    raw_test = m.group(1).strip() if m else ""
    out["test"] = raw_test or None
    if m:
        out["evidence"]["test"] = _line(r"Test:.*", text)

    out["lab"] = next((lab for lab in LABS if lab.lower().replace(" ", "") in text.lower().replace(" ", "")), None)

    m = re.search(r"Result:\s*([\d.]+)\s*([A-Za-zµ/<>\s]+?)\s*$", text, flags=re.IGNORECASE | re.MULTILINE)
    if m:
        out["value"] = float(m.group(1))
        out["unit"] = m.group(2).strip()
        out["evidence"]["result"] = _line(r"Result:.*", text)
    else:
        out["value"] = None
        out["unit"] = None

    m = re.search(r"Specification:\s*(.+)", text, flags=re.IGNORECASE)
    out["spec_text"] = m.group(1).strip() if m else None
    if m:
        out["evidence"]["spec_text"] = _line(r"Specification:.*", text)

    m = re.search(r"Method:\s*(.+)", text, flags=re.IGNORECASE)
    out["method"] = m.group(1).strip() if m else None
    if m:
        out["evidence"]["method"] = _line(r"Method:.*", text)

    return out


def extract_coa_llm(text, api_key, model="openai/gpt-4o-mini"):
    """LLM extraction for CoAs the deterministic parser cannot read."""
    prompt = (
        "Extract fields from this certificate of analysis. Reply with JSON only: "
        '{"sample_id": str|null, "test": str|null, "lab": str|null, '
        '"value": number|null, "unit": str|null, "spec_text": str|null, '
        '"method": str|null}. Do not invent values that are not stated.\n\n' + text
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(re.search(r"\{.*\}", content, flags=re.DOTALL).group(0))
    parsed["evidence"] = {}
    return parsed


def extract_coa(text, api_key=None):
    """Returns (extracted, route) where route says how it was read."""
    parsed = parse_coa_text(text)
    if parsed.get("sample_id") and parsed.get("value") is not None:
        return parsed, "document parser (deterministic)"
    if api_key:
        return extract_coa_llm(text, api_key), "language model (key from Secrets)"
    raise ValueError(
        "This CoA could not be read by the deterministic parser, and no API "
        "key is configured in Secrets for the language-model route."
    )
