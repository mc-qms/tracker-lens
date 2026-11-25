"""Read the messy tracker spreadsheets — read-only — and normalize them.

Every loader returns (records, FileReport). A file that cannot be read
into the expected shape is reported with the reason, never silently
skipped: a lens that hides a broken source is worse than the sprawl.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y", "%d %b %Y")


def parse_date(value):
    """Parse the date formats real trackers actually contain."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class FileReport:
    filename: str
    status: str  # "ok" | "failed"
    rows: int = 0
    message: str = ""


def _norm(name):
    return str(name).strip().lower()


def _find_column(df, candidates, label):
    """Find a column by synonym; return (actual_name, None) or (None, error)."""
    lookup = {_norm(c): c for c in df.columns}
    for cand in candidates:
        if cand in lookup:
            return lookup[cand], None
    found = ", ".join(str(c) for c in df.columns)
    return None, f"expected a {label} column ({' / '.join(candidates)}); found: {found}"


def _read(path):
    return pd.read_excel(path, engine="openpyxl", dtype=object)


def normalize_status(raw):
    s = str(raw or "").strip().lower()
    if s == "received":
        return "RECEIVED"
    if s in ("done", "complete", "completed", "reported", "closed"):
        return "COMPLETE"
    return "SENT"  # sent / waiting / in transit / blank all mean: still out


SAMPLE_ID = ["sample id", "sample #", "sample no", "sample"]


def load_sample_log(path):
    name = os.path.basename(path)
    try:
        df = _read(path)
    except Exception as e:  # unreadable file
        return [], FileReport(name, "failed", 0, f"could not be opened: {e}")
    col, err = _find_column(df, SAMPLE_ID, "sample identifier")
    if err:
        return [], FileReport(name, "failed", 0, err)
    mat_col, _ = _find_column(df, ["material"], "material")
    date_col, _ = _find_column(df, ["date received", "received"], "date received")
    records = []
    for _, row in df.iterrows():
        sid = str(row[col]).strip()
        if not sid or sid.lower() == "nan":
            continue
        records.append({
            "sample_id": sid,
            "material": str(row[mat_col]).strip() if mat_col else "",
            "received": parse_date(row[date_col]) if date_col else None,
        })
    return records, FileReport(name, "ok", len(records), "loaded")


def load_testing_tracker(path):
    name = os.path.basename(path)
    try:
        df = _read(path)
    except Exception as e:
        return [], FileReport(name, "failed", 0, f"could not be opened: {e}")
    cols = {}
    for key, cands, label in [
        ("sample_id", SAMPLE_ID, "sample identifier"),
        ("test", ["test", "assay"], "test"),
        ("lab", ["lab", "contract lab", "ctl"], "lab"),
        ("sent", ["date sent", "sent", "date shipped"], "date sent"),
        ("tat", ["promised (days)", "tat", "turnaround (days)", "promised"], "promised turnaround"),
        ("status", ["status"], "status"),
    ]:
        col, err = _find_column(df, cands, label)
        if err:
            return [], FileReport(name, "failed", 0, err)
        cols[key] = col
    result_col, _ = _find_column(df, ["result", "results"], "result")
    records = []
    for _, row in df.iterrows():
        sid = str(row[cols["sample_id"]]).strip()
        if not sid or sid.lower() == "nan":
            continue
        try:
            tat = int(float(row[cols["tat"]]))
        except (TypeError, ValueError):
            tat = None
        result = None
        if result_col:
            raw = row[result_col]
            if raw is not None and str(raw).strip().lower() != "nan":
                result = str(raw).strip()
        records.append({
            "sample_id": sid,
            "test": str(row[cols["test"]]).strip(),
            "lab": str(row[cols["lab"]]).strip(),
            "sent": parse_date(row[cols["sent"]]),
            "tat_days": tat,
            "status": normalize_status(row[cols["status"]]),
            "result": result,
        })
    return records, FileReport(name, "ok", len(records), "loaded")


def load_em(path):
    name = os.path.basename(path)
    try:
        df = _read(path)
    except Exception as e:
        return [], FileReport(name, "failed", 0, f"could not be opened: {e}")
    cols = {}
    for key, cands, label in [
        ("date", ["date"], "date"),
        ("room", ["room", "area"], "room"),
        ("result", ["result (cfu)", "result", "cfu"], "result"),
    ]:
        col, err = _find_column(df, cands, label)
        if err:
            return [], FileReport(name, "failed", 0, err)
        cols[key] = col
    type_col, _ = _find_column(df, ["type", "sample type"], "type")
    loc_col, _ = _find_column(df, ["location"], "location")
    records = []
    for _, row in df.iterrows():
        try:
            value = float(row[cols["result"]])
        except (TypeError, ValueError):
            continue
        records.append({
            "date": parse_date(row[cols["date"]]),
            "room": str(row[cols["room"]]).strip(),
            "location": str(row[loc_col]).strip() if loc_col else "",
            "type": str(row[type_col]).strip() if type_col else "",
            "result": value,
        })
    return records, FileReport(name, "ok", len(records), "loaded")


def load_stability(path):
    """The stability tracker uses 'Specimen' — no sample identifier column
    the lens recognises. It fails, on purpose, and says why."""
    name = os.path.basename(path)
    try:
        df = _read(path)
    except Exception as e:
        return [], FileReport(name, "failed", 0, f"could not be opened: {e}")
    col, err = _find_column(df, SAMPLE_ID, "sample identifier")
    if err:
        return [], FileReport(name, "failed", 0, err)
    return [], FileReport(name, "ok", 0, "loaded")


def load_arrivals(path):
    """The arrivals register: one row per CoA that has landed, with a
    Reviewed disposition column. Written by plumbing (a Power Automate
    flow in a real shop); read by the lens like every other source."""
    name = os.path.basename(path)
    try:
        df = _read(path)
    except Exception as e:
        return [], FileReport(name, "failed", 0, f"could not be opened: {e}")
    col, err = _find_column(df, SAMPLE_ID, "sample identifier")
    if err:
        return [], FileReport(name, "failed", 0, err)
    test_col, _ = _find_column(df, ["test"], "test")
    lab_col, _ = _find_column(df, ["lab", "laboratory"], "lab")
    date_col, _ = _find_column(df, ["date", "date received", "received date"], "date")
    att_col, _ = _find_column(df, ["attachment", "file"], "attachment")
    rev_col, _ = _find_column(df, ["reviewed", "acknowledged"], "reviewed")
    records = []
    for _, row in df.iterrows():
        sid = str(row[col]).strip()
        if not sid or sid.lower() == "nan":
            continue
        raw_rev = str(row[rev_col]).strip().lower() if rev_col else ""
        records.append({
            "sample_id": sid,
            "test": str(row[test_col]).strip() if test_col else "",
            "lab": str(row[lab_col]).strip() if lab_col else "",
            "date": parse_date(row[date_col]) if date_col else None,
            "attachment": str(row[att_col]).strip() if att_col else "",
            "reviewed": raw_rev in ("yes", "y", "true", "reviewed", "acknowledged"),
        })
    return records, FileReport(name, "ok", len(records), "loaded")


def load_all(data_dir, today=None):
    """Load every source, then date-shift the whole set together so the
    demo is always current: the newest shipped sample is 1 day old.
    One shift for all files keeps cross-file relationships intact."""
    today = today or date.today()
    samples, r1 = load_sample_log(os.path.join(data_dir, "sample_log.xlsx"))
    tests, r2 = load_testing_tracker(os.path.join(data_dir, "testing_tracker.xlsx"))
    em, r3 = load_em(os.path.join(data_dir, "em_trending.xlsx"))
    _, r4 = load_stability(os.path.join(data_dir, "stability_tracker.xlsx"))
    arrivals, r5 = load_arrivals(os.path.join(data_dir, "arrivals.xlsx"))
    reports = [r1, r2, r3, r4, r5]

    sent_dates = [t["sent"] for t in tests if t["sent"]]
    shift = 0
    if sent_dates:
        shift = (today - max(sent_dates)).days - 1
    if shift:
        delta = timedelta(days=shift)
        for s in samples:
            if s["received"]:
                s["received"] += delta
        for t in tests:
            if t["sent"]:
                t["sent"] += delta
        for e in em:
            if e["date"]:
                e["date"] += delta
        for a in arrivals:
            if a["date"]:
                a["date"] += delta
    return {
        "samples": samples,
        "tests": tests,
        "em": em,
        "arrivals": arrivals,
        "reports": reports,
        "shift_days": shift,
        "today": today,
    }
