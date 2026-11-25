import os

from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
at = AppTest.from_file(APP, default_timeout=60)
at.run()
assert not at.exception, at.exception
print("tabs:", [t.label for t in at.tabs])
md = "\n".join(m.value for m in at.markdown)
assert "Here's the update for today" in md, "digest missing"
assert "due in 2 days" in md, "due-soon line missing"
assert "stability_tracker.xlsx could not be read" in md, "provenance missing"
print("digest + provenance OK")
inbox = [s for s in at.selectbox if s.label == "Inbox"]
assert inbox, "inbox selectbox not found"
inbox[0].set_value("coa_fl107_endotoxin.txt").run()
btns = [b for b in at.button if "Read and review" in b.label]
assert btns, "CoA button not found"
btns[0].click().run()
assert not at.exception, at.exception
codes = [c.value for c in at.code]
assert any("FL-107" in c for c in codes), f"proposed update missing: {codes}"
print("CoA flow OK:", [c for c in codes if "FL-107" in c][0].replace("\n", " | "))
print("SMOKE TEST PASSED")
