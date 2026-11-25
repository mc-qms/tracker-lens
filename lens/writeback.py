"""The writes in the demo — made by the user, never by the lens.

When the lens knows something the trackers do not (a CoA has arrived;
the tracker row still shows the test as out), the Today tab offers the
user buttons. Clicking one is the user writing: this module performs
exactly those writes and nothing else.

Every write is keyed, never positional: the row is found by Sample #
and Test, and the value lands in a named column. Rows move when
people sort; keys do not. The match must be unambiguous — if the key
matches zero rows or more than one, nothing is written.
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
