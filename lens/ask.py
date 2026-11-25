"""Ask the lens: questions about the trackers, answered from the
computed snapshot — never from the raw sheets, never improvised.

The discipline is the same as the digest's. Python has already
computed every state, due date, and day count; this module routes a
question to the relevant slice of that snapshot and phrases the
answer from it, naming the source file. If the snapshot does not
contain the answer, the answer is that the trackers don't say —
an honest non-answer beats a fluent invention.

In the connected version, a language model can phrase these same
facts more freely. The facts it may use are the ones computed here.
"""
from __future__ import annotations

import re

LABELS = {
    "OVERDUE": "overdue",
    "DUE_SOON": "due soon",
    "IN_PROGRESS": "in progress",
    "AWAITING_REVIEW": "back — awaiting review",
    "COMPLETE": "complete",
}

CAN_ANSWER = (
    "I can answer about: what's overdue, what's due soon, what's "
    "back awaiting review, a specific sample (try “FL-106”), a "
    "specific test or lab, or EM excursions."
)


def _when(t):
    if t["state"] == "OVERDUE":
        return f"{abs(t['days'])} day{'s' if abs(t['days']) != 1 else ''} past its promised date"
    if t["state"] == "DUE_SOON":
        if t["days"] == 0:
            return "due today"
        if t["days"] == 1:
            return "due tomorrow"
        return f"due in {t['days']} days"
    if t["state"] == "AWAITING_REVIEW":
        return "the CoA is back, awaiting review"
    if t["state"] == "COMPLETE":
        return f"complete{f' — result {t['result']}' if t['result'] else ''}"
    return "in progress"


def _line(t):
    return (f"**{t['sample_id']} {t['test']}** ({t['lab']}) — "
            f"{LABELS[t['state']]}: {_when(t)}.")


def _list(rows, source, empty):
    if not rows:
        return empty
    return "\n".join(f"- {_line(t)}" for t in rows) + f"\n\n*(Source: {source})*"


def answer(question, enriched, excursions):
    q = (question or "").strip().lower()
    if not q:
        return "Ask me something about the trackers. " + CAN_ANSWER

    # Why-questions: the trackers record what, never why.
    if q.startswith("why") or " why " in q:
        m = re.search(r"fl-\d+", q)
        facts_line = ""
        if m:
            rows = [t for t in enriched if t["sample_id"].lower() == m.group(0)]
            if rows:
                facts_line = " What the trackers do say: " + " ".join(_line(t) for t in rows)
        return ("The trackers don't say why — they record dates, labs, "
                "and statuses, not reasons." + facts_line)

    # A specific sample.
    m = re.search(r"fl-\d+", q)
    if m:
        sid = m.group(0).upper()
        rows = [t for t in enriched if t["sample_id"] == sid]
        if not rows:
            return (f"No sample {sid} appears in the trackers. "
                    + CAN_ANSWER)
        return _list(rows, "testing_tracker.xlsx", "")

    # EM / excursions.
    if any(w in q for w in ("em", "environmental", "excursion", "cfu", "microbial")):
        if not excursions:
            return "No EM excursions in the current data. *(Source: em_trending.xlsx)*"
        lines = [
            f"- **{e['room']}**, {e['location']} — {e['result']:g} CFU against a "
            f"{'action' if e['level'] == 'ACTION' else 'alert'} limit of "
            f"{e['action'] if e['level'] == 'ACTION' else e['alert']} ({e['date']:%b %d})."
            for e in excursions
        ]
        return "\n".join(lines) + "\n\n*(Source: em_trending.xlsx)*"

    # A specific lab.
    for frag in ("meridian", "pacific", "clearline"):
        if frag in q:
            rows = [t for t in enriched if frag in t["lab"].lower()
                    and t["state"] != "COMPLETE"]
            lab = rows[0]["lab"] if rows else frag.title()
            return _list(rows, "testing_tracker.xlsx",
                         f"Nothing open at {lab} right now.")

    # A specific test.
    for name in ("endotoxin", "bioburden", "sterility", "toc"):
        if name in q:
            rows = [t for t in enriched if t["test"].lower() == name]
            return _list(rows, "testing_tracker.xlsx",
                         f"No {name} tests in the tracker.")

    # States.
    if "overdue" in q or "late" in q:
        rows = sorted([t for t in enriched if t["state"] == "OVERDUE"],
                      key=lambda t: t["days"])
        return _list(rows, "testing_tracker.xlsx", "Nothing is overdue.")
    if "awaiting" in q or "review" in q or "back" in q:
        rows = [t for t in enriched if t["state"] == "AWAITING_REVIEW"]
        return _list(rows, "testing_tracker.xlsx",
                     "Nothing is back awaiting review.")
    if "due" in q:
        rows = sorted([t for t in enriched if t["state"] == "DUE_SOON"],
                      key=lambda t: t["days"])
        return _list(rows, "testing_tracker.xlsx", "Nothing is due soon.")
    if "complete" in q or "done" in q or "finished" in q:
        rows = [t for t in enriched if t["state"] == "COMPLETE"]
        return _list(rows, "testing_tracker.xlsx", "Nothing is complete yet.")

    # Overview / fallback.
    if any(w in q for w in ("status", "open", "how many", "summary", "update")):
        open_rows = [t for t in enriched if t["state"] != "COMPLETE"]
        over = [t for t in enriched if t["state"] == "OVERDUE"]
        awaiting = [t for t in enriched if t["state"] == "AWAITING_REVIEW"]
        return (
            f"{len(open_rows)} outsourced tests are still open. "
            f"{len(over)} overdue, {len(awaiting)} back awaiting review. "
            "Ask me about any sample, lab, or test for the detail.\n\n"
            "*(Source: testing_tracker.xlsx)*"
        )
    return ("The trackers don't answer that. " + CAN_ANSWER)
