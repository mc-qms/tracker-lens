"""The write-back — performed for the user, never by the lens itself.

The collected sheet has one designated column: the tracker's
recorded Status. When the user edits that column, this module writes
the change through to the source workbook — exactly one cell, in the
row keyed by Sample # and Test. Nothing else in the demo writes, and
nothing writes on its own.

In a real Excel shop this module is the Power Automate flow: the
query view cannot take the edit, so a flow routes it to the source
workbook's "Update a row" action — keyed, like this, because rows
move when people sort and keys do not. The match must be
unambiguous: zero or multiple matches and nothing is written.
"""
from __future__ import annotations

import os

import openpyxl

TRACKER_FILE = "testing_tracker.xlsx"
TRACKER_SHEET = "CTL Tracker 2026"
ARRIVALS_FILE = "arrivals.xlsx"
ARRIVALS_SHEET = "Arrivals"


def _set_cell(data_dir, filename, sheet, sample_id, test_name, column, value):
    """Set one cell, located by (Sample #, Test) and column name.
    Returns a record of the write; raises ValueError, writing
    nothing, unless the key matches exactly one row."""
    path = os.path.join(data_dir, filename)
    wb = openpyxl.load_workbook(path)
    ws = wb[sheet]
    headers = [c.value for c in ws[1]]
    id_col = headers.index("Sample #")
    test_col = headers.index("Test")
    target_col = headers.index(column)

    matches = []
    for row in ws.iter_rows(min_row=2):
        if (row[id_col].value == sample_id
                and str(row[test_col].value).strip() == test_name):
            matches.append(row[target_col])
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one row in {filename} for {sample_id} / "
            f"{test_name}; found {len(matches)} — nothing written"
        )
    cell = matches[0]
    old = cell.value
    cell.value = value
    wb.save(path)
    return {
        "file": filename,
        "sheet": sheet,
        "sample_id": sample_id,
        "test": test_name,
        "column": column,
        "old": old,
        "new": value,
    }


def set_status(data_dir, sample_id, test_name, new_status):
    """The designated-column write: the user edited the recorded
    Status of one row of the collected sheet, and the edit is written
    through to the testing tracker, keyed by Sample # and Test."""
    return _set_cell(data_dir, TRACKER_FILE, TRACKER_SHEET,
                     sample_id, test_name, "Status", new_status)


def mark_received(data_dir, sample_id, test_name):
    """The user records, in the testing tracker, that a CoA is back:
    Status -> RECEIVED (the lens then shows the CoA as back; the same
    handling files the arrival as Reviewed in the register)."""
    return _set_cell(data_dir, TRACKER_FILE, TRACKER_SHEET,
                     sample_id, test_name, "Status", "RECEIVED")


def mark_reviewed(data_dir, sample_id, test_name):
    """The user dispositions an arrival: Reviewed -> Yes in the
    arrivals register. The arrival leaves the daily list; the record
    of it stays."""
    return _set_cell(data_dir, ARRIVALS_FILE, ARRIVALS_SHEET,
                     sample_id, test_name, "Reviewed", "Yes")
