"""Build data-crunching/momentum.ipynb (the website page) from the executed notebooks/momentum_ciz.ipynb.

The page keeps the notebook's code and saved outputs; Quarto renders it without re-executing.
Run after re-executing the notebook:  python3 _tools/make_momentum_page.py
"""
import copy
import os
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "notebooks", "momentum_ciz.ipynb")
DEST = os.path.join(ROOT, "data-crunching", "momentum.ipynb")

FRONT_MATTER = """---
title: "Momentum"
subtitle: "Jegadeesh and Titman (1993)"
---"""

HEADER = """<dl class="meta-row">
<dt>Paper</dt><dd><a href="https://www.jstor.org/stable/2328882">Jegadeesh, N. and S. Titman (1993), Returns to Buying Winners and Selling Losers, <em>Journal of Finance</em></a></dd>
<dt>Data</dt><dd>CRSP monthly stock file, <code>msf_v2</code> <span class="tag ciz">CIZ format</span></dd>
<dt>Sample</dt><dd>NYSE and AMEX common stocks, January 1965 to June 2026</dd>
<dt>Author</dt><dd>Qingyi (Freda) Song Drechsler</dd>
</dl>

<div class="btn-row">
<a class="primary" href="../notebooks/momentum_ciz.ipynb" download>Download notebook (.ipynb)</a>
</div>

This code replicates the methodology of Jegadeesh and Titman (1993). Momentum portfolios are formed based on past 3-12 months returns. This is a relatively simple Python application as it involves only one database, which is CRSP, and main variable of interest, cumulative past return, is fairly easy to compute."""

src = nbf.read(SRC, as_version=4)
page = copy.deepcopy(src)
# The notebook's own H1 title line is replaced by the page title and header; its intro text stays.
for c in page.cells:
    if c.cell_type == "markdown" and c.source.lstrip().startswith("# "):
        c.source = c.source.lstrip().split("\n", 1)[1].strip() if "\n" in c.source.strip() else ""
body = [c for c in page.cells if not (c.cell_type == "markdown" and not c.source.strip())]
page.cells = [nbf.v4.new_raw_cell(FRONT_MATTER), nbf.v4.new_markdown_cell(HEADER)] + body
nbf.write(page, DEST)
print(f"wrote {os.path.relpath(DEST, ROOT)} ({len(page.cells)} cells)")
