"""Build website pages (data-crunching/*.ipynb) from executed notebooks in notebooks/.

Each page keeps the notebook's code and saved outputs; Quarto renders it without re-executing.
Run after re-executing a notebook:  python3 _tools/make_page.py [momentum|fama-french ...]
"""
import copy
import os
import sys
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = {
    "momentum": dict(
        src="notebooks/momentum_ciz.ipynb",
        dest="data-crunching/momentum.ipynb",
        title="Momentum",
        subtitle="Jegadeesh and Titman (1993)",
        meta=[
            ("Paper", '<a href="https://www.jstor.org/stable/2328882">Jegadeesh, N. and S. Titman (1993), Returns to Buying Winners and Selling Losers, <em>Journal of Finance</em></a>'),
            ("Data", 'CRSP monthly stock file, <code>msf_v2</code> <span class="tag ciz">CIZ format</span>'),
            ("Sample", "NYSE and AMEX common stocks, January 1965 to June 2026"),
            ("Author", "Qingyi (Freda) Song Drechsler"),
        ],
        intro="This code replicates the methodology of Jegadeesh and Titman (1993). Momentum portfolios are formed based on past 3-12 months returns. This is a relatively simple Python application as it involves only one database, which is CRSP, and main variable of interest, cumulative past return, is fairly easy to compute.",
    ),
    "fama-french": dict(
        src="notebooks/ff3_crspCIZ.ipynb",
        dest="data-crunching/fama-french.ipynb",
        title="Fama–French 3-Factor Model",
        subtitle="Fama and French (1993)",
        meta=[
            ("Paper", '<a href="https://www.sciencedirect.com/science/article/pii/0304405X93900235">Fama, E. and K. French (1993), Common Risk Factors in the Returns on Stocks and Bonds, <em>Journal of Financial Economics</em></a>'),
            ("Data", 'CRSP monthly stock file, <code>msf_v2</code> <span class="tag ciz">CIZ format</span>; Compustat annual fundamentals; CRSP/Compustat link table'),
            ("Sample", "NYSE, AMEX and NASDAQ common stocks, factors through June 2026"),
            ("Author", "Qingyi (Freda) Song Drechsler"),
        ],
        intro="This set of Python code replicates the Fama French risk factors SMB and HML, in addition to the excess market risk factor. It utilizes CRSP data for pricing related items and Compustat data for fundamental data.",
    ),
    "iclink": dict(
        src="notebooks/iclink_ciz.ipynb",
        dest="data-crunching/iclink.ipynb",
        title="Linking IBES and CRSP (ICLINK)",
        subtitle="IBES TICKER to CRSP PERMNO link table",
        meta=[
            ("Source", 'WRDS SAS macro <a href="https://wrds-www.wharton.upenn.edu/pages/wrds-research/macros/wrds-macro-iclink-ciz/">ICLINK (CIZ format)</a>'),
            ("Data", 'IBES identifier file <code>ibes.id</code>; CRSP names file <code>stocknames_v2</code> <span class="tag ciz">CIZ format</span>'),
            ("Output", "IBES TICKER–CRSP PERMNO links, scored from 0 (best) to 6"),
            ("Author", "Qingyi (Freda) Song Drechsler"),
        ],
        intro="""This Python code builds a linkage between IBES data (containing information on company earnings and analysts forecasts) and CRSP data (containing price and return information). It builds the linkage in two layers:

- linking through CUSIPs
- linking through Tickers

As CUSIPs are more reliable company identifiers, we first try to match as much as possible through it. For the remaining ones that are not matched through CUSIP, we turn to TICKER as last resort. To impose additional layer of quality check, I add a company name matching layer on top of matching through CUSIPs and TICKERs. Name matching is done through FuzzyWuzzy package, but there can be many other fuzzy name matching methods.""",
    ),
}


def header(p):
    rows = "\n".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in p["meta"])
    nb_name = os.path.basename(p["src"])
    return f"""<dl class="meta-row">
{rows}
</dl>

<div class="btn-row">
<a class="primary" href="../notebooks/{nb_name}" download>Download notebook (.ipynb)</a>
</div>

{p["intro"]}"""


def build(name):
    p = PAGES[name]
    page = copy.deepcopy(nbf.read(os.path.join(ROOT, p["src"]), as_version=4))
    # A notebook H1 title line is replaced by the page title and header; any intro text under it stays.
    for c in page.cells:
        if c.cell_type == "markdown" and c.source.lstrip().startswith("# "):
            c.source = c.source.lstrip().split("\n", 1)[1].strip() if "\n" in c.source.strip() else ""
    body = [c for c in page.cells if not (c.cell_type == "markdown" and not c.source.strip())]
    front = f'---\ntitle: "{p["title"]}"\nsubtitle: "{p["subtitle"]}"\n---'
    page.cells = [nbf.v4.new_raw_cell(front), nbf.v4.new_markdown_cell(header(p))] + body
    nbf.write(page, os.path.join(ROOT, p["dest"]))
    print(f"wrote {p['dest']} ({len(page.cells)} cells)")


if __name__ == "__main__":
    for name in sys.argv[1:] or PAGES:
        build(name)
