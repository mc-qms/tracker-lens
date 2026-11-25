"""Generate the deliberately messy demo spreadsheets for Tracker Lens.

Fictitious Labs Inc. data. Dates are written relative to an anchor in
the past; the loader date-shifts everything at runtime so the demo is
always current. Run: python3 tools/make_data.py
"""
import os
from datetime import date, timedelta

from openpyxl import Workbook

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ANCHOR = date(2026, 1, 12)  # "demo now" at generation time; loader re-anchors


def d(offset):
    return ANCHOR + timedelta(days=offset)


# ---------------------------------------------------------------- sample log
wb = Workbook()
ws = wb.active
ws.title = "Samples"
ws.append(["Sample ID", "Date Received", "Material", "Type", "Requested By", "Storage Location"])
samples = [
    ("FL-101", -9, "Purified Water — WFI Loop 3", "Water", "J. Alvarez", "QC Micro bench"),
    ("FL-102", -8, "Buffer Intermediate B-220", "In-process", "M. Okafor", "Cold room 2"),
    ("FL-103", -14, "Polysorbate 80, NF", "Raw material", "S. Patel", "RM warehouse"),
    ("FL-104", -18, "Drug Product DP-11, vial", "Finished product", "J. Alvarez", "Cold room 1"),
    ("FL-105", -30, "DP-11 Stability, 3-month", "Stability", "QA Stability", "Stability chamber B"),
    ("FL-106", -5, "Purified Water — WFI Loop 1", "Water", "J. Alvarez", "QC Micro bench"),
    ("FL-107", -11, "Sucrose, NF", "Raw material", "S. Patel", "RM warehouse"),
    ("FL-108", -10, "In-process Bulk IB-88", "In-process", "M. Okafor", "Cold room 2"),
    ("FL-109", -13, "Human Serum Albumin, 25%", "Raw material", "S. Patel", "Cold room 1"),
    ("FL-110", -6, "Drug Product DP-11, vial", "Finished product", "J. Alvarez", "Cold room 1"),
    ("FL-111", -17, "Final rinse, CIP skid 2", "Cleaning", "D. Nguyen", "QC Micro bench"),
    ("FL-112", -30, "DP-11 Stability, 6-month", "Stability", "QA Stability", "Stability chamber B"),
]
for sid, off, mat, typ, req, loc in samples:
    ws.append([sid, d(off), mat, typ, req, loc])
wb.save(os.path.join(BASE, "sample_log.xlsx"))

# ------------------------------------------------------- outsourced testing
wb = Workbook()
ws = wb.active
ws.title = "CTL Tracker 2026"
ws.append(["Sample #", "Test", "Lab", "Date Sent", "Promised (days)", "Status", "Result"])
# Date Sent deliberately mixed: real dates, US strings, "Nov 3, 2026" strings.
tests = [
    ("FL-101", "Endotoxin", "Pacific BioTest", d(-1), 5, "Sent", None),
    ("FL-101", "TOC", "Meridian Analytical", "Jan 11, 2026", 3, "Sent", None),
    ("FL-102", "Bioburden", "Pacific BioTest", d(-6), 7, "Sent", None),
    ("FL-102", "Endotoxin", "Pacific BioTest", "01/06/2026", 7, "Sent", None),
    ("FL-103", "Endotoxin", "Meridian Analytical", d(-12), 7, "waiting", None),
    ("FL-104", "Sterility", "ClearLine Labs", d(-16), 14, "waiting", None),
    ("FL-106", "Endotoxin", "Pacific BioTest", d(-3), 5, "Sent", None),
    ("FL-107", "Endotoxin", "Pacific BioTest", d(-9), 7, "RECEIVED", None),
    ("FL-108", "Bioburden", "Meridian Analytical", d(-8), 10, "Sent", None),
    ("FL-109", "Bioburden", "Pacific BioTest", d(-11), 10, "RECEIVED", None),
    ("FL-110", "Sterility", "ClearLine Labs", "Jan 8, 2026", 14, "Sent", None),
    ("FL-111", "TOC", "Meridian Analytical", d(-15), 5, "done", "212 ppb"),
]
for row in tests:
    ws.append(list(row))
wb.save(os.path.join(BASE, "testing_tracker.xlsx"))

# --------------------------------------------------------------------- EM
wb = Workbook()
ws = wb.active
ws.title = "EM 2026"
ws.append(["Date", "Room", "Location", "Type", "Result (CFU)", "Tech"])
em_rows = []
for room_name, series in [
    ("Grade B — Filling Suite", [0, 1, 2, 1, 3, 2, 1, 0, 2, 1]),
    ("Grade C — Prep Room", [8, 11, 9, 14, 12, 18, 16, 22, 19, 27]),
    ("Grade D — Corridor", [22, 30, 26, 35, 28, 41, 33, 29, 38, 31]),
]:
    loc = "Air, centre of room"
    for i, v in enumerate(series):
        em_rows.append((d(-49 + i * 5), room_name, loc, "Viable air", v, "T. Rivera"))
# planted excursions in Grade B
em_rows.append((d(-12), "Grade B — Filling Suite", "Air, centre of room", "Viable air", 7, "T. Rivera"))
em_rows.append((d(-5), "Grade B — Filling Suite", "Air, by filler", "Viable air", 12, "T. Rivera"))
em_rows.append((d(-5), "Grade B — Filling Suite", "Surface, filler bench", "Surface", 4, "T. Rivera"))
em_rows.sort(key=lambda r: r[0])
for row in em_rows:
    ws.append(list(row))
wb.save(os.path.join(BASE, "em_trending.xlsx"))

# ------------------------------------------- stability tracker (the broken one)
wb = Workbook()
ws = wb.active
ws.title = "Stability"
ws.append(["Specimen", "Product", "Pull Window", "Condition"])
stab = [
    ("STB-221", "DP-11", "3 month", "2–8 °C"),
    ("STB-222", "DP-11", "3 month", "25 °C / 60% RH"),
    ("STB-231", "DP-11", "6 month", "2–8 °C"),
    ("STB-232", "DP-11", "6 month", "25 °C / 60% RH"),
    ("STB-241", "DP-12", "1 month", "2–8 °C"),
    ("STB-242", "DP-12", "1 month", "-20 °C"),
]
for row in stab:
    ws.append(list(row))
wb.save(os.path.join(BASE, "stability_tracker.xlsx"))

# ----------------------------------------------------------------- arrivals
# The arrivals register: in a real shop a Power Automate flow appends a
# row here when a contract lab's CoA email lands. The Reviewed column is
# the disposition — the daily view shows only unreviewed arrivals.
wb = Workbook()
ws = wb.active
ws.title = "Arrivals"
ws.append(["Date", "Sample #", "Test", "Lab", "Attachment", "Reviewed"])
arrivals = [
    (d(-4), "FL-107", "Endotoxin", "Pacific BioTest", "coa_fl107_endotoxin.txt", "Yes"),
    (d(-3), "FL-109", "Bioburden", "Pacific BioTest", "coa_fl109_bioburden.txt", "Yes"),
    (d(0), "FL-106", "Endotoxin", "Pacific BioTest", "coa_fl106_endotoxin.txt", None),
]
for row in arrivals:
    ws.append(list(row))
wb.save(os.path.join(BASE, "arrivals.xlsx"))

print("wrote 5 spreadsheets to", BASE)
