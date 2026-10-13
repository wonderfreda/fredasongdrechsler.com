"""Build notebooks/dgtw_ciz.ipynb from the legacy DGTW page (kept in notebooks/originals/dgtw.qmd).

Freda's prose and code are kept. Changes:
  - CRSP CIZ: monthly returns, prices and shares from crsp_m_stock.msf_v2, which carries the
    security attributes on each record (no msenames join); legacy shrcd 10/11 becomes the CIZ
    common-stock filter used in her CIZ Fama-French code; NYSE breakpoints use primaryexch == 'N'
    instead of exchcd == 1; date/ret/prc/cfacpr/cfacshr become mthcaldt/mthret/mthprc/
    mthcumfacpr/mthcumfacshr; CCM from crsp_m_ccm.
  - Sample extended from 1970-2017 to January 1970 - June 2026.
  - .copy() on two slices that are modified afterwards (pandas SettingWithCopyWarning).
  - The SAS comparison chart (SAS output not available) is replaced by a Plotly chart of the
    corner DGTW benchmark portfolios; code formatted with black so lines fit the code box.
"""
import os
import re
import subprocess
import textwrap
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "notebooks", "originals", "dgtw.qmd")
DEST = os.path.join(ROOT, "notebooks", "dgtw_ciz.ipynb")
UVX = os.path.expanduser("~/.local/bin/uvx")

body = open(PAGE).read().split("---", 2)[2]
segments = re.split(r"(```python\n.*?```)", body, flags=re.S)
code_blocks = [s[len("```python\n"):-3].rstrip("\n") for s in segments if s.startswith("```python")]
assert len(code_blocks) == 10, len(code_blocks)
# trailing whitespace on code lines is dropped (invisible, and it breaks exact-match edits)
blocks = {i: "\n".join(l.rstrip() for l in b.splitlines()) for i, b in enumerate(code_blocks, start=1)}

# ---- block 1: header and imports ----------------------------------------------------------
EDITS = [
    (1, "# Updated: April 2021                    #",
        "# Updated: April 2021                    #\n# Updated: October 2026, CRSP CIZ format #"),
    (1, "import matplotlib.pyplot as plt\n",
        "import plotly.graph_objects as go\nimport plotly.io as pio\n"),
    (1, "from pandas.tseries.offsets import *\n",
        "from pandas.tseries.offsets import *\n\npio.renderers.default = 'notebook_connected'\n"),
]

# ---- block 2: CRSP block, rewritten for msf_v2 ----------------------------------------------
crsp_old_start = blocks[2].index("# sql similar to crspmerge macro")
crsp_old_end = blocks[2].index("# price adjusted")
blocks[2] = blocks[2][:crsp_old_start] + '''# sql similar to crspmerge macro
# CRSP CIZ format: msf_v2 carries the security attributes on each monthly
# record, so no separate names-file merge is needed.
# Common stocks only: equivalent to legacy shrcd = 10 or 11.
# No exchange restriction, as in the SAS version.

crsp_m = conn.raw_sql("""
    select distinct permno, permco, cusip, mthcaldt, siccd, primaryexch,
           mthret, mthvol, shrout, mthprc, mthcumfacpr, mthcumfacshr
    from crsp_m_stock.msf_v2
    where mthcaldt between '01/01/1970' and '06/30/2026'
    and sharetype='NS' and securitytype='EQTY' and securitysubtype='COM'
    and usincflg='Y' and issuertype in ('ACOR', 'CORP')
    """, date_cols = ['mthcaldt'])

# change variable format to int
crsp_m[['permco','permno']]=crsp_m[['permco','permno']].astype(int)

# Line up date to be end of month
crsp_m['jdate']=crsp_m['mthcaldt']+MonthEnd(0)

''' + blocks[2][crsp_old_end:]

EDITS += [
    (2, "crsp_m['p']=crsp_m['prc'].abs()/crsp_m['cfacpr']", "crsp_m['p']=crsp_m['mthprc'].abs()/crsp_m['mthcumfacpr']"),
    (2, "crsp_m['tso']=crsp_m['shrout']*crsp_m['cfacshr']*1e3", "crsp_m['tso']=crsp_m['shrout']*crsp_m['mthcumfacshr']*1e3"),
    # ---- block 4: CCM from the monthly update
    (4, "from crsp.ccmxpf_linktable", "from crsp_m_ccm.ccmxpf_linktable"),
    # ---- block 8: CIZ mthret includes the delisting return, so a -100% month can occur;
    #      log(0) = -inf gives the correct -100% cumulative return, without the numpy warning
    (8, "_tmp_crsp['logret']=np.log(1+_tmp_crsp['ret'])",
        "# CIZ returns include delisting returns: a -100% month gives log(0) = -inf,\n"
        "# which correctly yields a -100% cumulative return\n"
        "with np.errstate(divide='ignore'):\n"
        "    _tmp_crsp['logret']=np.log(1+_tmp_crsp['ret'])"),
    # ---- block 9: NYSE breakpoints
    (9, "nyse = sizemom[sizemom['exchcd']==1]", "nyse = sizemom[sizemom['primaryexch']=='N']"),
    # ---- block 10: copies of slices that are modified afterwards
    (10, "port4 = port3[['permno','gvkey','date','size','mom','bm_adj','dgtw_port']]",
         "port4 = port3[['permno','gvkey','date','size','mom','bm_adj','dgtw_port']].copy()"),
    (10, "crsp_m1= crsp_m[['permno','date','ret']]", "crsp_m1= crsp_m[['permno','date','ret']].copy()"),
]
for b, old, new in EDITS:
    assert old in blocks[b], f"block {b}: {old[:70]!r}"
    blocks[b] = blocks[b].replace(old, new)

# ---- CRSP field names downstream: in these blocks 'date' and 'ret' always refer to CRSP --------
for b in (4, 8, 9, 10):
    blocks[b] = (blocks[b].replace("'date'", "'mthcaldt'").replace("'ret'", "'mthret'")
                          .replace("'exchcd'", "'primaryexch'"))

# ---- chart: corner DGTW benchmark portfolios ------------------------------------------------
CHART = '''# Growth of $1 in the corner DGTW benchmark portfolios
# dgtw_port = size quintile + book-to-market quintile + momentum quintile
CORNERS = [('111', 'Small, low B/M, low momentum', '#2a78d6'),
           ('115', 'Small, low B/M, high momentum', '#eb6834'),
           ('551', 'Big, high B/M, low momentum', '#1baf7a'),
           ('555', 'Big, high B/M, high momentum', '#eda100')]

_w = dgtw_vwret.pivot(index='mthcaldt', columns='dgtw_port',
                      values='dgtw_vwret').sort_index()
fig = go.Figure()
for port, label, color in CORNERS:
    growth = (1 + _w[port].fillna(0)).cumprod()
    fig.add_trace(go.Scatter(
        x=growth.index, y=growth, name=f'{port}: {label}', mode='lines',
        line=dict(color=color, width=2), customdata=_w[port],
        hovertemplate='$%{y:,.2f} (month: %{customdata:+.1%})'
                      '<extra>' + port + '</extra>'))
    fig.add_annotation(x=growth.index[-1], y=np.log10(growth.iloc[-1]),
                       text=f'<b>{port}</b> ' + (f'${growth.iloc[-1]:,.0f}'
                                                 if growth.iloc[-1] >= 10
                                                 else f'${growth.iloc[-1]:,.2f}'),
                       showarrow=False, xanchor='left', xshift=8,
                       font=dict(size=12, color='#0b0b0b'))
_g = pd.concat([(1 + _w[p].fillna(0)).cumprod() for p, _, _ in CORNERS])
ticks = [10**e for e in range(-2, 8) if _g.min() / 10 <= 10**e <= _g.max() * 10]
fig.update_layout(
    title=dict(text='DGTW Benchmark Portfolios: Growth of $1'
                    '<br><sup style="color:#52514e">Corner portfolios of the '
                    'size / book-to-market / momentum sort, value-weighted, '
                    f'{_w.index[0]:%b %Y}\\u2013{_w.index[-1]:%b %Y}</sup>',
               x=0, xanchor='left'),
    template='plotly_white', height=540, margin=dict(l=70, r=110, t=90, b=130),
    font=dict(family='Inter, system-ui, sans-serif', size=13, color='#0b0b0b'),
    paper_bgcolor='#fcfcfb', plot_bgcolor='#fcfcfb', hovermode='x unified',
    legend=dict(orientation='h', x=0, y=-0.12, yanchor='top'),
    xaxis=dict(showgrid=False, ticks='outside', tickcolor='#c3c2b7',
               linecolor='#c3c2b7', range=[_w.index[0], _w.index[-1]]),
    yaxis=dict(type='log', title='Growth of $1 (log scale)',
               tickvals=ticks, ticktext=[f'${v:,.2g}' if v < 1 else f'${v:,.0f}' for v in ticks],
               gridcolor='#ecebe7', zeroline=False),
)
fig.show()'''


# ---- formatting: SQL re-indented, black (single quotes kept) ---------------------------------
def reindent_sql(src):
    def fix(m):
        sql = textwrap.dedent(m.group(2).strip("\n")).strip("\n")
        sql = "\n".join(("    " + l) if l.strip() else "" for l in sql.splitlines())
        return f'{m.group(1)}"""\n{sql}\n    """'
    return re.sub(r'(raw_sql\(\s*f?)"""(.*?)"""', fix, src, flags=re.S)


def black(src):
    out = subprocess.run([UVX, "black", "-q", "--line-length", "75", "--skip-string-normalization", "-"],
                         input=src, capture_output=True, text=True, check=True)
    return out.stdout.rstrip("\n")


for b in blocks:
    blocks[b] = black(reindent_sql(blocks[b]))
CHART = black(CHART)

# long comments split at natural points
LINE_WRAP = [
    ("# BE = stockholders' equity + deferred taxes + investment tax credit - Preferred Stock",
     "# BE = stockholders' equity + deferred taxes + investment tax credit\n#      - Preferred Stock"),
    ("# Edit December 2020: correct the division by 0 problem caused by missing market cap",
     "# Edit December 2020: correct the division by 0 problem caused by\n# missing market cap"),
    ("# pick max datadate for a given permno year combo (firm changes fiscal period)",
     "# pick max datadate for a given permno year combo\n# (firm changes fiscal period)"),
]
for o, n in LINE_WRAP:
    hits = [b for b in blocks if o in blocks[b]]
    assert hits, o
    for b in hits:
        blocks[b] = blocks[b].replace(o, n)

# Closing paragraphs: the SAS comparison was for the legacy version; the chart now shows the
# corner portfolios (user-approved wording)
TEXT_EDITS = [
    ("The correlation between the two dgtw_vwret series is 99.4%, with p-value equals 0.0.",
     "When this comparison was run on the original (legacy CRSP) version of this code, the correlation "
     "between the two dgtw_vwret series was 99.4%, with p-value equals 0.0."),
    ("I also plot the time series of the corner portfolios below to provide a visual comparison between the "
     "two series. The DGTW portfolio is ordered by Size, Book-to-Market and Momentum. The blue solid line "
     "represents the value-weighted portfolio return from the Python output (dgtw_vwret), and the dash red line "
     "reports the result from the SAS output.",
     "I also plot the corner portfolios below, as the growth of $1 invested in each from July 1971 through "
     "June 2026. The DGTW portfolio is ordered by Size, Book-to-Market and Momentum, so portfolio 111 holds the "
     "smallest stocks with the lowest book-to-market and momentum, and portfolio 555 the largest stocks with "
     "the highest."),
]
for o, _ in TEXT_EDITS:
    assert o in body, o[:60]

# ---- assemble -------------------------------------------------------------------------------
cells = []
bi = 0
for seg in segments:
    if seg.startswith("```python"):
        bi += 1
        cells.append(nbf.v4.new_code_cell(blocks[bi]))
        continue
    text = re.sub(r'<div class="btn-row">.*?</div>\n*', "", seg, flags=re.S)       # legacy "Full Code" link
    for o, n in TEXT_EDITS:
        text = text.replace(o, n)
    has_chart = "images/data-crunching_dgtw/1.png" in text
    text = re.sub(r"!\[\]\(\.\./images/data-crunching_dgtw/\d+\.png\)\n*", "", text)
    if text.strip():
        cells.append(nbf.v4.new_markdown_cell(text.strip()))
    if has_chart:
        cells.append(nbf.v4.new_code_cell(CHART))

too_long = [l for c in cells if c.cell_type == "code" for l in c.source.splitlines() if len(l) > 75]
nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, DEST)
print(f"wrote {os.path.relpath(DEST, ROOT)}: {sum(c.cell_type == 'code' for c in cells)} code cells")
for l in too_long:
    print(f"  long line ({len(l)}): {l}")
