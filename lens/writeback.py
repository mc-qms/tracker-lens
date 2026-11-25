"""The one write in the demo — made by the user, never by the lens.

When the lens knows something the tracker does not (a CoA has arrived;
the tracker row still shows the test as out), the Today tab offers the
user a button. Clicking it is the user writing: this module performs
exactly that write and nothing else.

The write is keyed, never positional: the row is found by Sample #
and Test, and the value lands in the named Status column. Rows move
when people sort; keys do not. The match must be unambiguous — if the
key matches zero rows or more than one, nothing is written.
"""
from __future__ import annotations

import os

import openpyxl

TRACKER_FILE = "testing_tracker.xlsx"
SHEET = "CTL Tracker 2026"


def mark_received(data_dir, sample_id, test_name):
    """Set the Status cell of one tracker row to RECEIVED.

    Returns a record of the write (file, sheet, key, column, old and
    new values) so the caller can show the user exactly what changed.
    Raises ValueError, writing nothing, unless the key matches
    exactly one row.
    """
    path = os.path.join(data_dir, TRACKER_FILE)
    wb = openpyxl.load_workbook(path)
    ws = wb[SHEET]
    headers = [c.value for c in ws[1]]
    id_col = headers.index("Sample #")
    test_col = headers.index("Test")
    status_col = headers.index("Status")

    matches = []
    for row in ws.iter_rows(min_row=2):
        if (row[id_col].value == sample_id
                and str(row[test_col].value).strip() == test_name):
            matches.append(row[status_col])
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one tracker row for {sample_id} / "
            f"{test_name}; found {len(matches)} — nothing written"
        )
    cell = matches[0]
    old = cell.value
    cell.value = "RECEIVED"
    wb.save(path)
    return {
        "file": TRACKER_FILE,
        "sheet": SHEET,
        "sample_id": sample_id,
        "test": test_name,
        "column": "Status",
        "old": old,
        "new": "RECEIVED",
    }
