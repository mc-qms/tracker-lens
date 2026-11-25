"""The morning digest: deterministic facts, plain-language wording.

Every number in the digest is computed by lens.core / lens.loaders.
The wording is a template over those facts — small, checkable claims,
plus a provenance line that reports the state of the sources
themselves, including the ones that failed to load.
"""
from __future__ import annotations


def build_facts(enriched_tests, excursions, reports):
    overdue = sorted([t for t in enriched_tests if t["state"] == "OVERDUE"],
                     key=lambda t: t["days"])
    due_soon = sorted([t for t in enriched_tests if t["state"] == "DUE_SOON"],
                      key=lambda t: t["days"])
    awaiting = [t for t in enriched_tests if t["state"] == "AWAITING_REVIEW"]
    open_tests = [t for t in enriched_tests if t["state"] not in ("COMPLETE",)]
    labs = sorted({t["lab"] for t in open_tests})
    return {
        "overdue": overdue,
        "due_soon": due_soon,
        "awaiting": awaiting,
        "open_count": len(open_tests),
        "labs": labs,
        "excursions": excursions,
        "reports": reports,
    }


def _days_phrase(days):
    if days == 0:
        return "due today"
    if days == 1:
        return "due tomorrow"
    return f"due in {days} days"


def render_digest(facts):
    lines = []
    n_open = facts["open_count"]
    labs = facts["labs"]
    lines.append(
        f"Here's the update for today. {n_open} outsourced test"
        f"{'s are' if n_open != 1 else ' is'} still open across "
        f"{len(labs)} contract lab{'s' if len(labs) != 1 else ''} "
        f"({', '.join(labs)})."
    )
    for t in facts["overdue"]:
        lines.append(
            f"**Overdue:** {t['sample_id']} {t['test']} at {t['lab']} is "
            f"{abs(t['days'])} day{'s' if abs(t['days']) != 1 else ''} past its promised date."
        )
    for t in facts["due_soon"]:
        lines.append(f"{t['sample_id']} {t['test']} at {t['lab']} is {_days_phrase(t['days'])}.")
    if facts["awaiting"]:
        items = ", ".join(f"{t['sample_id']} {t['test']}" for t in facts["awaiting"])
        lines.append(f"Back and waiting for review: {items}.")
    for e in facts["excursions"]:
        if e["level"] == "ACTION":
            lines.append(
                f"**EM action excursion:** {e['room']}, {e['location']} — "
                f"{e['result']:g} CFU against an action limit of {e['action']} "
                f"({e['date']:%b %d})."
            )
        else:
            lines.append(
                f"EM alert: {e['room']}, {e['location']} — {e['result']:g} CFU "
                f"against an alert limit of {e['alert']} ({e['date']:%b %d})."
            )
    if not facts["overdue"] and not facts["excursions"]:
        lines.append("Nothing is overdue and there are no open EM excursions.")

    ok = [r for r in facts["reports"] if r.status == "ok"]
    bad = [r for r in facts["reports"] if r.status != "ok"]
    prov = "Sources read this morning: " + ", ".join(
        f"{r.filename} ({r.rows} rows)" for r in ok) + "."
    for r in bad:
        prov += (f" **{r.filename} could not be read** — {r.message}. "
                 f"Anything tracked only in that file is not in today's picture.")
    lines.append(prov)
    return lines
