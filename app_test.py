"""Headless test of the Streamlit app: renders all tabs and reports exceptions + timing."""
import time
from streamlit.testing.v1 import AppTest

t = time.time()
at = AppTest.from_file("app.py", default_timeout=300).run()
print(f"Initial render: {time.time()-t:.1f}s")
print("Exceptions:", [e.value for e in at.exception] or "none")
print("Errors:", [e.value for e in at.error] or "none")
print("Warnings:", [w.value[:100] for w in at.warning])

# Change a priority slider (water saving to max) and re-run
t = time.time()
at.slider(key="w_water_saving").set_value(1.0).run()
print(f"\nRe-render after slider change: {time.time()-t:.1f}s")
print("Exceptions:", [e.value for e in at.exception] or "none")

# Change scenario sliders
at.sidebar.slider[0].set_value(2.0).run()
print("Scenario run exceptions:", [e.value for e in at.exception] or "none")
print("Expanders:", [e.label for e in at.expander][:12])
