"""Build website pages (data-crunching/*.ipynb) from executed notebooks in notebooks/.

Each page keeps the notebook's code and saved outputs; Quarto renders it without re-executing.
Run after re-executing a notebook:  python3 _tools/make_page.py [momentum|fama-french ...]
"""
import copy
import os
import re
import sys
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_COLUMN_PX = 650   # width of the site's text column


def table_too_wide(html):
    """Estimate a rendered output table's width from its header and cell text (compact table style)."""
    html = re.sub(r"<style.*?</style>", "", html, flags=re.S)
    rows = [[re.sub(r"<[^>]+>", "", cell).strip() for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)]
            for r in re.findall(r"<tr.*?>(.*?)</tr>", html, re.S)]
    rows = [r for r in rows if r]
    if not rows:
        return False
    ncol = max(len(r) for r in rows)
    chars = [min(max((len(r[i]) for r in rows if i < len(r)), default=0), 26) for i in range(ncol)]
    return sum(chars) * 7.2 + ncol * 16 > TEXT_COLUMN_PX

def direct_plotly(nb):
    """Load Plotly with a plain <script> tag instead of through require.js.

    Plotly's notebook_connected output loads plotly.js with require.js, which Quarto then adds to the
    page; that raises "Mismatched anonymous define()" and can leave a chart blank, depending on
    script timing. Here the loader becomes a plain script tag (once per page) and each chart's
    require(["plotly"], ...) wrapper a plain function call.
    """
    loaded = False
    for c in nb.cells:
        for o in c.get("outputs", []):
            html = o.get("data", {}).get("text/html")
            if html is None:
                continue
            html = "".join(html) if isinstance(html, list) else html
            if "requirejs.config" in html:
                url = re.search(r"'plotly': \['([^']+)'\]", html).group(1)
                # Quarto still loads require.js for any page with HTML output, so define() is hidden
                # before plotly.js loads (otherwise plotly registers as a require module and leaves
                # no global Plotly). It stays hidden: nothing later on the page uses require.js, and
                # Quarto's zenscroll.js, loaded at the end, would otherwise raise "Mismatched
                # anonymous define()" too.
                html = "" if loaded else (
                    '<script>window.define = undefined;</script>\n'
                    f'<script src="{url}.js" charset="utf-8"></script>')
                loaded = True
            elif 'require(["plotly"], function(Plotly) {' in html:
                html = html.replace('require(["plotly"], function(Plotly) {', "(function() {")
                head, sep, tail = html.rpartition("});")
                html = head + "})();" + tail
            o["data"]["text/html"] = html
    return nb


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

As CUSIPs are more reliable company identifiers, we first try to match as much as possible through it. For the remaining ones that are not matched through CUSIP, we turn to TICKER as last resort. To impose additional layer of quality check, I add a company name matching layer on top of matching through CUSIPs and TICKERs. Name matching is done through RapidFuzz package (the successor to FuzzyWuzzy), but there can be many other fuzzy name matching methods.""",
    ),
    "textual-analysis": dict(
        src="notebooks/textual_analysis_sp500_ciz.ipynb",
        dest="textual-analysis/textual-analysis-on-sp500-companies.ipynb",
        title="Textual Analysis on S&P500 Companies",
        subtitle="Bag of words and Doc2Vec on company business descriptions",
        meta=[
            ("Data", 'S&P 500 membership and identifiers from CRSP (<code>msp500list_v2</code>, <code>msf_v2</code>, <code>stksecurityinfohist</code>) <span class="tag ciz">CIZ format</span>; business descriptions from Compustat and Capital IQ'),
            ("Sample", "S&P 500 companies as of December 2020"),
            ("Methods", "Text cleaning with NLTK and spaCy, bag of words with scikit-learn, Doc2Vec with gensim"),
            ("Author", "Qingyi (Freda) Song Drechsler"),
        ],
        intro="",
    ),
    "pead": dict(
        src="notebooks/pead_ciz.ipynb",
        dest="data-crunching/pead.ipynb",
        title="Post-Earnings Announcement Drift",
        subtitle="Livnat and Mendenhall (2006)",
        meta=[
            ("Paper", '<a href="https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1475-679X.2006.00196.x">Livnat, J. and R. Mendenhall (2006), Comparing the Post-Earnings Announcement Drift for Surprises Calculated from Analyst and Time Series Forecasts, <em>Journal of Accounting Research</em></a>'),
            ("Data", 'CRSP daily stock file <code>dsf_v2</code>, daily market index and S&P 500 list <code>msp500list_v2</code> <span class="tag ciz">CIZ format</span>; IBES estimates and actuals; Compustat quarterly fundamentals'),
            ("Sample", "S&P 500 members, fiscal quarters January 2010 to June 2026"),
            ("Author", "Qingyi (Freda) Song Drechsler"),
        ],
        intro="",
    ),
    "dgtw": dict(
        src="notebooks/dgtw_ciz.ipynb",
        dest="data-crunching/dgtw.ipynb",
        title="Characteristics-Based Benchmarks (DGTW)",
        subtitle="Daniel, Grinblatt, Titman and Wermers (1997)",
        meta=[
            ("Paper", '<a href="https://onlinelibrary.wiley.com/doi/full/10.1111/j.1540-6261.1997.tb02724.x">Daniel, K., M. Grinblatt, S. Titman and R. Wermers (1997), Measuring Mutual Fund Performance with Characteristic-Based Benchmarks, <em>Journal of Finance</em></a>'),
            ("Data", 'CRSP monthly stock file, <code>msf_v2</code> <span class="tag ciz">CIZ format</span>; Compustat annual fundamentals; CRSP/Compustat link table'),
            ("Sample", "CRSP common stocks, January 1970 to June 2026"),
            ("Author", "Qingyi (Freda) Song Drechsler"),
        ],
        intro="",
    ),
    "io_breadth": dict(
        src="notebooks/io_breadth_ciz.ipynb",
        dest="data-crunching/io_breadth.ipynb",
        title="Institutional Ownership Breadth",
        subtitle="Chen, Hong and Stein (2002)",
        meta=[
            ("Paper", '<a href="https://www.sciencedirect.com/science/article/pii/S0304405X02002234">Chen, J., H. Hong and J. Stein (2002), Breadth of Ownership and Stock Returns, <em>Journal of Financial Economics</em></a>'),
            ("Data", 'Thomson Reuters 13F holdings (<code>tfn.s34type1</code>, <code>s34type3</code>); CRSP monthly stock file <code>msf_v2</code> and <code>stksecurityinfohist</code> <span class="tag ciz">CIZ format</span>'),
            ("Sample", "CRSP common stocks, 13F report dates March 1980 to December 2025 (Q1 2026 left out: Vanguard's holdings are not yet in the 13F data on WRDS)"),
            ("Author", "Qingyi (Freda) Song Drechsler"),
        ],
        intro="",
    ),
    "exchange-rate": dict(
        src="notebooks/exchange_rate.ipynb",
        dest="intro-to-python-for-fnce/exchange-rate.ipynb",
        title="Exchange Rate",
        subtitle="Exchange rate data on WRDS: Compustat Global, Worldscope and Datastream",
        meta=[
            ("Data", "Compustat Global <code>g_exrt_mth</code>; Worldscope <code>wsinfo</code>, <code>wsndata</code>; Datastream <code>ds2fxcode</code>, <code>ds2fxrate</code>"),
            ("Example", "Chinese Yuan (CNY) per US Dollar (USD)"),
            ("Author", "Qingyi (Freda) Song Drechsler"),
        ],
        intro="",
    ),
    "wrds-sec": dict(
        src="notebooks/wrds_sec.ipynb",
        dest="textual-analysis/wrds-sec.ipynb",
        title="WRDS SEC",
        subtitle="SEC indices and filings on WRDS",
        meta=[
            ("Data", "WRDS SEC Analytics Suite: <code>wrdssec.wciklink_names</code>, <code>forms</code>, <code>wrds_forms</code>; filings on the WRDS server (<code>/wrds/sec/wrds_clean_filings</code>)"),
            ("Example", "10-K filings of Apple (AAPL) and Wells Fargo (WFC), 2015 to 2021"),
            ("Author", "Qingyi (Freda) Song Drechsler"),
        ],
        intro="",
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
    # Table outputs too wide for the text column use the page width instead
    for c in page.cells:
        if c.cell_type == "code" and any(
                table_too_wide(o["data"]["text/html"])
                for o in c.get("outputs", []) if "text/html" in o.get("data", {}) and "<table" in o["data"]["text/html"]):
            c.source = "#| column: page\n" + c.source
    body = [c for c in page.cells if not (c.cell_type == "markdown" and not c.source.strip())]
    front = f'---\ntitle: "{p["title"]}"\nsubtitle: "{p["subtitle"]}"\n---'
    page.cells = [nbf.v4.new_raw_cell(front), nbf.v4.new_markdown_cell(header(p))] + body
    direct_plotly(page)
    nbf.write(page, os.path.join(ROOT, p["dest"]))
    print(f"wrote {p['dest']} ({len(page.cells)} cells)")


if __name__ == "__main__":
    for name in sys.argv[1:] or PAGES:
        build(name)
