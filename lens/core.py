"""Deterministic core: due-date math, specification checks, EM limits.

Nothing in this module guesses. Dates, limits, and comparisons are
computed here so they can be tested; the language model never touches
a number that matters.
"""
from __future__ import annotations

from datetime import timedelta

# Demo specifications for outsourced tests (a real deployment reads
# these from the governing specification documents).
SPECS = {
    "Endotoxin": {"op": "<", "limit": 0.25, "unit": "EU/mg", "label": "< 0.25 EU/mg"},
    "Bioburden": {"op": "<=", "limit": 100.0, "unit": "CFU/g", "label": "NMT 100 CFU/g"},
    "TOC": {"op": "<=", "limit": 500.0, "unit": "ppb", "label": "NMT 500 ppb"},
}

# Demo EM limits for viable-air results, CFU: (alert, action) by area grade.
EM_LIMITS = {
    "Grade B": (5, 10),
    "Grade C": (25, 50),
    "Grade D": (50, 100),
}


def enrich_tests(tests, today):
    """Add due_date, state, and day counts to each tracker row."""
    out = []
    for t in tests:
        row = dict(t)
        if t["sent"] and t["tat_days"]:
            row["due"] = t["sent"] + timedelta(days=t["tat_days"])
        else:
            row["due"] = None
        if t["status"] == "COMPLETE":
            row["state"] = "COMPLETE"
            row["days"] = None
        elif t["status"] == "RECEIVED":
            row["state"] = "AWAITING_REVIEW"
            row["days"] = None
        elif row["due"] is None:
            row["state"] = "IN_PROGRESS"
            row["days"] = None
        else:
            delta = (row["due"] - today).days
            row["days"] = delta
            if delta < 0:
                row["state"] = "OVERDUE"
            elif delta <= 2:
                row["state"] = "DUE_SOON"
            else:
                row["state"] = "IN_PROGRESS"
        out.append(row)
    return out


def grade_of(room):
    for grade in EM_LIMITS:
        if room.startswith(grade):
            return grade
    return None


def em_excursions(em):
    """Viable-air results above the alert limit, worst first."""
    found = []
    for e in em:
        if e["type"].strip().lower() != "viable air":
            continue
        grade = grade_of(e["room"])
        if not grade:
            continue
        alert, action = EM_LIMITS[grade]
        if e["result"] > action:
            level = "ACTION"
        elif e["result"] > alert:
            level = "ALERT"
        else:
            continue
        found.append({**e, "grade": grade, "alert": alert, "action": action, "level": level})
    found.sort(key=lambda x: (x["level"] != "ACTION", -(x["date"].toordinal() if x["date"] else 0)))
    return found


def _spec_for(test_name):
    for key, spec in SPECS.items():
        if key.lower() in test_name.lower():
            return key, spec
    return None, None


def _passes(value, spec):
    if spec["op"] == "<":
        return value < spec["limit"]
    return value <= spec["limit"]


def review_coa(extracted, tests):
    """First-pass review of an extracted CoA against the tracker and the
    specification. Every check carries the evidence it rests on."""
    checks = []
    sid = extracted.get("sample_id")
    test_name = extracted.get("test") or ""
    ev = extracted.get("evidence", {})

    open_rows = [t for t in tests if t["sample_id"] == sid and t["status"] != "COMPLETE"]
    matched = None
    for t in open_rows:
        if t["test"].lower() in test_name.lower() or test_name.lower() in t["test"].lower():
            matched = t
            break
    if matched is None and open_rows:
        matched = open_rows[0]

    checks.append({
        "label": "Sample is on the testing tracker",
        "status": "PASS" if matched else "FLAG",
        "detail": (f"{sid} — {matched['test']} at {matched['lab']}" if matched
                   else f"{sid} not found among open tracker rows"),
        "evidence": ev.get("sample_id", ""),
    })

    spec_key, spec = _spec_for(test_name)
    value = extracted.get("value")
    if spec and value is not None:
        ok = _passes(value, spec)
        checks.append({
            "label": "Result within specification",
            "status": "PASS" if ok else "FLAG",
            "detail": f"{value:g} {spec['unit']} against {spec['label']}",
            "evidence": ev.get("result", ""),
        })
    elif spec_key is None and value is not None:
        checks.append({
            "label": "Result within specification",
            "status": "FLAG",
            "detail": f"no demo specification registered for '{test_name}'; a human must compare it",
            "evidence": ev.get("result", ""),
        })

    for field, label in [("method", "Method stated on the CoA"),
                         ("lab", "Testing laboratory identified"),
                         ("spec_text", "Specification stated on the CoA")]:
        present = bool(extracted.get(field))
        checks.append({
            "label": label,
            "status": "PASS" if present else "FLAG",
            "detail": str(extracted.get(field)) if present else "missing — ask the lab to reissue or confirm",
            "evidence": ev.get(field, ""),
        })

    verdict = "PASS" if all(c["status"] == "PASS" for c in checks) else "FLAGS"
    return {"checks": checks, "verdict": verdict, "matched": matched, "spec": spec, "spec_key": spec_key}


def proposed_update(extracted, review):
    """The exact tracker edit for a human to type in — addressed by
    sample ID and column name, never by row number (rows move when
    people sort). The lens proposes; the human writes."""
    sid = extracted.get("sample_id")
    value, unit = extracted.get("value"), extracted.get("unit") or ""
    oos = any(c["label"] == "Result within specification" and c["status"] == "FLAG"
              for c in review["checks"])
    result_text = f"{value:g} {unit}".strip() if value is not None else "(see CoA)"
    if oos:
        sets = [
            ("Status", "RECEIVED — result exceeds specification; escalate, do not close"),
            ("Result", f"{result_text} — exceeds {review['spec']['label']}" if review["spec"] else result_text),
        ]
    else:
        sets = [
            ("Status", "done"),
            ("Result", result_text),
        ]
    evidence = [c["evidence"] for c in review["checks"] if c["evidence"]]
    return {
        "file": "testing_tracker.xlsx",
        "key_column": "Sample #",
        "key_value": sid,
        "sets": sets,
        "evidence": evidence,
    }
