"""Tests for the Tracker Lens core. Run: python3 -m pytest tests/ -q"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lens import core, digest, extract, loaders, writeback

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TODAY = date(2026, 11, 24)


def loaded():
    return loaders.load_all(DATA, today=TODAY)


def test_parse_date_formats():
    assert loaders.parse_date("2026-01-05") == date(2026, 1, 5)
    assert loaders.parse_date("01/06/2026") == date(2026, 1, 6)
    assert loaders.parse_date("Jan 11, 2026") == date(2026, 1, 11)
    assert loaders.parse_date(None) is None
    assert loaders.parse_date("") is None


def test_load_reports():
    state = loaded()
    by_name = {r.filename: r for r in state["reports"]}
    assert by_name["sample_log.xlsx"].status == "ok"
    assert by_name["testing_tracker.xlsx"].status == "ok"
    assert by_name["em_trending.xlsx"].status == "ok"
    stab = by_name["stability_tracker.xlsx"]
    assert stab.status == "failed"
    assert "Specimen" in stab.message


def test_date_shift_keeps_demo_current():
    state = loaded()
    newest = max(t["sent"] for t in state["tests"])
    assert (TODAY - newest).days == 1


def test_enriched_states():
    state = loaded()
    enriched = core.enrich_tests(state["tests"], TODAY)
    by_key = {(t["sample_id"], t["test"]): t for t in enriched}
    assert by_key[("FL-103", "Endotoxin")]["state"] == "OVERDUE"
    assert by_key[("FL-103", "Endotoxin")]["days"] == -5
    assert by_key[("FL-104", "Sterility")]["state"] == "OVERDUE"
    assert by_key[("FL-104", "Sterility")]["days"] == -2
    assert by_key[("FL-101", "TOC")]["state"] == "DUE_SOON"
    assert by_key[("FL-101", "TOC")]["days"] == 2
    assert by_key[("FL-107", "Endotoxin")]["state"] == "AWAITING_REVIEW"
    assert by_key[("FL-111", "TOC")]["state"] == "COMPLETE"


def test_em_excursions():
    state = loaded()
    ex = core.em_excursions(state["em"])
    assert len(ex) == 3
    actions = [e for e in ex if e["level"] == "ACTION"]
    assert len(actions) == 1
    assert actions[0]["result"] == 12
    assert actions[0]["grade"] == "Grade B"


def _coa(name):
    with open(os.path.join(DATA, "coa_inbox", name), encoding="utf-8") as f:
        return f.read()


def test_clean_coa_passes():
    state = loaded()
    parsed, route = extract.extract_coa(_coa("coa_fl107_endotoxin.txt"))
    assert parsed["sample_id"] == "FL-107"
    assert parsed["value"] == 0.08
    review = core.review_coa(parsed, state["tests"])
    assert review["verdict"] == "PASS", review["checks"]
    update = core.proposed_update(parsed, review)
    assert update["key_value"] == "FL-107"
    assert ("Result", "0.08 EU/mg") in update["sets"]
    assert ("Status", "done") in update["sets"]


def test_oos_coa_flags():
    state = loaded()
    parsed, _ = extract.extract_coa(_coa("coa_fl109_bioburden.txt"))
    assert parsed["value"] == 140.0
    assert parsed["method"] is None
    review = core.review_coa(parsed, state["tests"])
    assert review["verdict"] == "FLAGS"
    flags = {c["label"] for c in review["checks"] if c["status"] == "FLAG"}
    assert "Result within specification" in flags
    assert "Method stated on the CoA" in flags
    update = core.proposed_update(parsed, review)
    assert "escalate" in dict(update["sets"])["Status"]


def _inbox_parsed():
    inbox = os.path.join(DATA, "coa_inbox")
    out = []
    for name in sorted(os.listdir(inbox)):
        with open(os.path.join(inbox, name), encoding="utf-8") as f:
            out.append(extract.parse_coa_text(f.read()))
    return out


def test_arrivals_detected():
    state = loaded()
    arrivals = core.find_arrivals(state["tests"], _inbox_parsed())
    # FL-106's CoA is in the inbox but its tracker row still says sent.
    # FL-107 and FL-109 are already marked received — not arrivals.
    assert [(a["sample_id"], a["test"]) for a in arrivals] == [("FL-106", "Endotoxin")]


def test_mark_received_writes_by_key(tmp_path):
    import openpyxl
    import shutil
    for name in ("sample_log.xlsx", "testing_tracker.xlsx",
                 "em_trending.xlsx", "stability_tracker.xlsx"):
        shutil.copy(os.path.join(DATA, name), tmp_path / name)
    rec = writeback.mark_received(str(tmp_path), "FL-106", "Endotoxin")
    assert rec["old"] == "Sent" and rec["new"] == "RECEIVED"
    wb = openpyxl.load_workbook(tmp_path / "testing_tracker.xlsx")
    ws = wb["CTL Tracker 2026"]
    cells = {(r[0].value, r[1].value): r[5].value for r in ws.iter_rows(min_row=2)}
    assert cells[("FL-106", "Endotoxin")] == "RECEIVED"
    assert cells[("FL-101", "Endotoxin")] == "Sent"  # same test, other sample: untouched
    assert cells[("FL-101", "TOC")] == "Sent"         # same sample, other test: untouched
    state = loaders.load_all(str(tmp_path), today=TODAY)
    enriched = core.enrich_tests(state["tests"], TODAY)
    fl106 = [t for t in enriched if t["sample_id"] == "FL-106"][0]
    assert fl106["state"] == "AWAITING_REVIEW"


def test_digest_facts_and_provenance():
    state = loaded()
    enriched = core.enrich_tests(state["tests"], TODAY)
    facts = digest.build_facts(enriched, core.em_excursions(state["em"]), state["reports"])
    assert len(facts["overdue"]) == 2
    assert len(facts["awaiting"]) == 2
    text = "\n".join(digest.render_digest(facts))
    assert "due in 2 days" in text
    assert "stability_tracker.xlsx could not be read" in text
    assert "Overdue" in text
