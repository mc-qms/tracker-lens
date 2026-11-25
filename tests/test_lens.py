"""Tests for the Tracker Lens core. Run: python3 -m pytest tests/ -q"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lens import ask, core, digest, extract, loaders, writeback

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
    assert by_key[("FL-107", "Endotoxin")]["state"] == "RETURNED"
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


def test_arrivals_detected():
    state = loaded()
    arrivals = core.find_arrivals(state["tests"], state["arrivals"])
    # FL-106's arrival is unreviewed and its tracker row still says
    # sent. FL-107 and FL-109 arrived too, but both are filed as
    # Reviewed in the register — they are not in the daily queue.
    assert [(a["sample_id"], a["test"]) for a in arrivals] == [("FL-106", "Endotoxin")]
    assert arrivals[0]["tracker_status"] == "SENT"


def _copy_data(tmp_path):
    import shutil
    for name in ("sample_log.xlsx", "testing_tracker.xlsx",
                 "em_trending.xlsx", "stability_tracker.xlsx", "arrivals.xlsx"):
        shutil.copy(os.path.join(DATA, name), tmp_path / name)


def test_mark_received_writes_by_key(tmp_path):
    import openpyxl
    _copy_data(tmp_path)
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
    assert fl106["state"] == "RETURNED"


def test_set_status_writes_through_keyed(tmp_path):
    import openpyxl
    _copy_data(tmp_path)
    rec = writeback.set_status(str(tmp_path), "FL-103", "Endotoxin", "RECEIVED")
    assert rec["column"] == "Status" and rec["new"] == "RECEIVED"
    assert rec["old"] == "waiting"  # the sheet's own free-text word for still-out
    wb = openpyxl.load_workbook(tmp_path / "testing_tracker.xlsx")
    ws = wb["CTL Tracker 2026"]
    cells = {(r[0].value, r[1].value): r[5].value for r in ws.iter_rows(min_row=2)}
    assert cells[("FL-103", "Endotoxin")] == "RECEIVED"
    assert cells[("FL-104", "Sterility")] == "waiting"  # other rows untouched
    assert cells[("FL-101", "Endotoxin")] == "Sent"
    state = loaders.load_all(str(tmp_path), today=TODAY)
    row = [t for t in state["tests"]
           if t["sample_id"] == "FL-103" and t["test"] == "Endotoxin"][0]
    assert row["status"] == "RECEIVED" and row["status_raw"] == "RECEIVED"
    try:
        writeback.set_status(str(tmp_path), "FL-999", "Endotoxin", "RECEIVED")
        raise AssertionError("unknown key should have raised")
    except ValueError:
        pass


def test_mark_reviewed_clears_the_queue(tmp_path):
    import openpyxl
    _copy_data(tmp_path)
    rec = writeback.mark_reviewed(str(tmp_path), "FL-106", "Endotoxin")
    assert rec["column"] == "Reviewed" and rec["new"] == "Yes"
    wb = openpyxl.load_workbook(tmp_path / "arrivals.xlsx")
    ws = wb["Arrivals"]
    cells = {(r[1].value, r[2].value): r[5].value for r in ws.iter_rows(min_row=2)}
    assert cells[("FL-106", "Endotoxin")] == "Yes"
    assert cells[("FL-107", "Endotoxin")] == "Yes"  # was already reviewed; unchanged
    state = loaders.load_all(str(tmp_path), today=TODAY)
    assert core.find_arrivals(state["tests"], state["arrivals"]) == []
    # The record stays: all three arrivals are still in the register.
    assert len(state["arrivals"]) == 3


def _ask(q):
    state = loaded()
    enriched = core.enrich_tests(state["tests"], TODAY)
    queue = core.find_arrivals(state["tests"], state["arrivals"])
    return ask.answer(q, enriched, core.em_excursions(state["em"]), queue)


def test_ask_overdue():
    out = _ask("What's overdue?")
    assert "FL-103" in out and "5 days past" in out
    assert "FL-104" in out and "2 days past" in out
    assert "testing_tracker.xlsx" in out


def test_ask_sample_and_unknown_sample():
    out = _ask("Status of FL-106?")
    assert "Endotoxin" in out and "Pacific BioTest" in out and "due in 2 days" in out
    out = _ask("Status of FL-999?")
    assert "No sample FL-999" in out


def test_ask_lab_awaiting_and_em():
    assert "FL-103" in _ask("What do we have at Meridian?")
    out = _ask("What's back awaiting review?")
    # The register is the source: FL-106 arrived unreviewed; FL-107 and
    # FL-109 are marked Reviewed on the sheet, so the lens must not
    # call them awaiting.
    assert "FL-106" in out and "arrivals.xlsx" in out
    assert "FL-107" not in out and "FL-109" not in out
    out = _ask("Any EM excursions?")
    assert "Grade B" in out and "12" in out


def test_ask_why_and_unanswerable():
    out = _ask("Why is FL-103 late?")
    assert "don't say why" in out and "FL-103" in out
    out = _ask("What's the weather like?")
    assert "don't answer that" in out


def test_digest_facts_and_provenance():
    state = loaded()
    enriched = core.enrich_tests(state["tests"], TODAY)
    queue = core.find_arrivals(state["tests"], state["arrivals"])
    facts = digest.build_facts(enriched, core.em_excursions(state["em"]),
                               state["reports"], queue)
    assert len(facts["overdue"]) == 2
    assert len(facts["awaiting"]) == 1
    assert facts["awaiting"][0]["sample_id"] == "FL-106"
    text = "\n".join(digest.render_digest(facts))
    assert "due in 2 days" in text
    assert "stability_tracker.xlsx could not be read" in text
    assert "Overdue" in text
