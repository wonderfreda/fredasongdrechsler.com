"""Build notebooks/maneuvering_wrds_data.ipynb, the "Full Code" download for the Maneuvering WRDS Data page.

The notebook is the page itself: its prose as markdown cells and its code blocks as code cells
(unexecuted; the output tables on the page are left out, the reader's own run produces them).
Rerun after editing intro-to-python-for-fnce/maneuvering-wrds-data.qmd.
"""
import os
import re
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "intro-to-python-for-fnce", "maneuvering-wrds-data.qmd")
DEST = os.path.join(ROOT, "notebooks", "maneuvering_wrds_data.ipynb")

body = open(PAGE).read().split("---", 2)[2]
body = re.sub(r"<!-- output:(\w+) -->.*?<!-- /output:\1 -->\n*", "", body, flags=re.S)  # page output tables
body = re.sub(r'<div class="btn-row">.*?</div>\n*', "", body, flags=re.S)               # the download button

cells = [nbf.v4.new_markdown_cell("# Maneuvering WRDS Data\n\nQingyi (Freda) Song Drechsler")]
for seg in re.split(r"(```python\n.*?```)", body, flags=re.S):
    if seg.startswith("```python"):
        cells.append(nbf.v4.new_code_cell(seg[len("```python\n"):-3].rstrip("\n")))
    elif seg.strip():
        cells.append(nbf.v4.new_markdown_cell(seg.strip()))

nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, DEST)
print(f"wrote {os.path.relpath(DEST, ROOT)}: {sum(c.cell_type == 'code' for c in cells)} code cells")
