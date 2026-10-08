"""Build notebooks/pead_ciz.ipynb from the legacy PEAD page (kept in notebooks/originals/pead.qmd).

Freda's prose and code are kept. Changes:
  - CRSP CIZ: S&P 500 universe from crsp_m_indexes.msp500list_v2; trading calendar and
    value-weighted market return from crsp_m_stock.wrds_dailyindexret_query (dlycaldt, vwretd);
    share adjustment factor, price, market cap and return from crsp_m_stock.dsf_v2
    (dlycumfacshr, dlyprc, dlycap, dlyret); CCM from crsp_m_ccm. dlycumfacshr follows the
    legacy cfacshr convention and dlycap equals abs(prc*shrout) (checked around AAPL's 2020 split).
  - Daily CRSP pulls limited to stocks that were ever S&P 500 members (the universe of the code).
  - Sample extended: IBES/Compustat periods Jan 2010 - Jun 2026, CRSP data Jan 2009 - Jun 2026.
  - SUEs cast to float (np.where with None left them as objects, which pd.qcut rejects).
  - missing linkenddt filled with today as a pandas Timestamp (not datetime.date; pandas
    deprecates comparing the two).
  - pd.offsets.MonthOffset(3) (not a pandas offset) -> pd.DateOffset(months=3).
  - The matplotlib chart is replaced by a Plotly chart in the site style; lines wrapped to fit.
"""
import os
import re
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "notebooks", "originals", "pead.qmd")
DEST = os.path.join(ROOT, "notebooks", "pead_ciz.ipynb")

body = open(PAGE).read().split("---", 2)[2]
segments = re.split(r"(```python\n.*?```)", body, flags=re.S)
code_blocks = [s[len("```python\n"):-3].rstrip("\n") for s in segments if s.startswith("```python")]
assert len(code_blocks) == 17, len(code_blocks)
# trailing whitespace on code lines is dropped (invisible, and it breaks exact-match edits)
blocks = {i: "\n".join(l.rstrip() for l in b.splitlines()) for i, b in enumerate(code_blocks, start=1)}

SP500_PERMNOS = "select distinct permno from crsp_m_indexes.msp500list_v2"

EDITS = [
    # ---- block 1: header, imports, sample period
    (1, "# Update: Jan 2021                  #",
        "# Update: Jan 2021                  #\n# Update: Oct 2026, CRSP CIZ format #"),
    (1, "import matplotlib.pyplot as plt\n", "import plotly.graph_objects as go\nimport plotly.io as pio\n"),
    (1, "import datetime\n", "import datetime\n\npio.renderers.default = 'notebook_connected'\n"),
    (1, "enddate = '12/31/2018'", "enddate = '06/30/2026'"),
    (1, "# set CRSP date range a bit wider to guarantee collecting all information\n"
        "crsp_begdate = '01/01/2009'\ncrsp_enddate = '12/31/2019'",
        "# set CRSP date range a bit wider to guarantee collecting all information\n"
        "# (CRSP data in this version ends in June 2026)\n"
        "crsp_begdate = '01/01/2009'\ncrsp_enddate = '06/30/2026'"),
    # ---- block 3: S&P 500 universe and CCM
    (3, "# New code uses crsp.msp500list", "# New code uses crsp.msp500list_v2 (CRSP CIZ format)"),
    (3, '''sp500 = conn.raw_sql(f"""
                        select a.*
                        from crsp.msp500list as a;
                        """, date_cols=['start', 'ending'])''',
        '''sp500 = conn.raw_sql("""
    select distinct permno, mbrstartdt, mbrenddt
    from crsp_m_indexes.msp500list_v2
    """, date_cols=['mbrstartdt', 'mbrenddt'])'''),
    (3, '''_ccm = conn.raw_sql(""" select gvkey, lpermco as permco, lpermno as permno,
                        linkdt, linkenddt
                        from crsp.ccmxpf_linktable
                        where usedflag=1
                        and linkprim in ('P', 'C')""", date_cols=['linkdt', 'linkenddt'])''',
        '''_ccm = conn.raw_sql("""
    select distinct gvkey, lpermco as permco, lpermno as permno,
           linkdt, linkenddt
    from crsp_m_ccm.ccmxpf_linktable
    where usedflag=1
    and linkprim in ('P', 'C')
    """, date_cols=['linkdt', 'linkenddt'])'''),
    (3, "_ccm['linkenddt'] = _ccm.linkenddt.fillna(datetime.date.today())",
        "_ccm['linkenddt'] = _ccm.linkenddt.fillna(pd.Timestamp.today().normalize())"),
    # ---- block 7: trading calendar
    (7, "# unique trade dates from crsp.dsi", "# unique trade dates from the CRSP daily index file"),
    (7, '''crsp_dats = conn.raw_sql("""
                            select date
                            from crsp.dsi
                         """, date_cols=['date'])''',
        '''crsp_dats = conn.raw_sql("""
    select distinct dlycaldt
    from crsp_m_stock.wrds_dailyindexret_query
    order by dlycaldt
    """, date_cols=['dlycaldt'])'''),
    (7, "tradedates = pd.merge(expand_anndats, crsp_dats, how='left', left_on=['prior_date'], right_on=['date'])",
        "tradedates = pd.merge(expand_anndats, crsp_dats, how='left',\n"
        "                      left_on=['prior_date'], right_on=['dlycaldt'])"),
    (7, "tradedates['dgap'] = tradedates.anndats-tradedates.date", "tradedates['dgap'] = tradedates.anndats-tradedates.dlycaldt"),
    (7, "tradedates = tradedates[['anndats', 'date']]", "tradedates = tradedates[['anndats', 'dlycaldt']]"),
    # ---- block 8: adjustment factors
    (8, '''cfacshr = conn.raw_sql(f"""
                        select permno, date, cfacshr
                        from crsp.dsf
                        where date between '{crsp_begdate}' and '{crsp_enddate}'
                        """, date_cols = ['date'])''',
        f'''cfacshr = conn.raw_sql(f"""
    select distinct permno, dlycaldt, dlycumfacshr
    from crsp_m_stock.dsf_v2
    where dlycaldt between '{{crsp_begdate}}' and '{{crsp_enddate}}'
    and permno in ({SP500_PERMNOS})
    """, date_cols = ['dlycaldt'])'''),
    (8, "ibes_anndats = pd.merge(ibes_anndats, cfacshr, how='left', on=['permno', 'date'])",
        "ibes_anndats = pd.merge(ibes_anndats, cfacshr, how='left',\n                        on=['permno', 'dlycaldt'])"),
    # ---- block 9
    (9, "ibes1 = ibes1.drop(['anndats','date'], axis=1).rename(columns={'cfacshr':'cfacshr_ann'})",
        "ibes1 = ibes1.drop(['anndats','dlycaldt'], axis=1)\\\n"
        "    .rename(columns={'dlycumfacshr':'cfacshr_ann'})"),
    (9, "ibes1 = ibes1.drop(['anndats','date'], axis=1).rename(columns={'cfacshr':'cfacshr_rep'})",
        "ibes1 = ibes1.drop(['anndats','dlycaldt'], axis=1)\\\n"
        "    .rename(columns={'dlycumfacshr':'cfacshr_rep'})"),
    # ---- block 12: next trading day after rdq
    (12, "eads1 = pd.merge(expand_rdq, crsp_dats, how='left', left_on=['post_date'], right_on=['date'])",
         "eads1 = pd.merge(expand_rdq, crsp_dats, how='left',\n"
         "                 left_on=['post_date'], right_on=['dlycaldt'])"),
    (12, "eads1['dgap'] = eads1.date-eads1.rdq", "eads1['dgap'] = eads1.dlycaldt-eads1.rdq"),
    (12, "#eads1 = eads1.loc[eads1.groupby('rdq')['dgap'].idxmin()].rename(columns={'date':'rdq1'})\n", ""),
    (12, "eads1 = eads1.reindex(eads1.groupby('rdq')['dgap'].idxmin()).rename(columns={'date':'rdq1'})",
         "eads1 = eads1.reindex(eads1.groupby('rdq')['dgap'].idxmin())\\\n"
         "    .rename(columns={'dlycaldt':'rdq1'})"),
    # ---- block 12: np.where(..., None) leaves the SUEs as object dtype, which pd.qcut rejects
    (12, "sue['sue3'] = (sue.act - sue.medest) / sue.prccq\n",
         "sue['sue3'] = (sue.act - sue.medest) / sue.prccq\n"
         "sue[['sue1','sue2','sue3']] = sue[['sue1','sue2','sue3']].astype(float)\n"),
    # ---- block 13: pd.offsets.MonthOffset does not exist in pandas; 3 months ahead is DateOffset(months=3)
    (13, "sue_final.rdq1 + pd.offsets.MonthOffset(3))", "sue_final.rdq1 + pd.DateOffset(months=3))"),
    # ---- block 14: daily returns
    (14, '''dsf = conn.raw_sql(f"""
                        select permno, date, prc, abs(prc*shrout) as mcap, ret from crsp.dsf
                        where date between '{crsp_begdate}' and '{crsp_enddate}'
                        """, date_cols = ['date'])''',
         f'''dsf = conn.raw_sql(f"""
    select distinct permno, dlycaldt, dlyprc, dlycap as mcap, dlyret
    from crsp_m_stock.dsf_v2
    where dlycaldt between '{{crsp_begdate}}' and '{{crsp_enddate}}'
    and permno in ({SP500_PERMNOS})
    """, date_cols = ['dlycaldt'])'''),
    (14, '''dsi = conn.raw_sql(f"""
                    select date, vwretd from crsp.dsi where date between '{crsp_begdate}' and '{crsp_enddate}'
                    """, date_cols=['date'])''',
         '''dsi = conn.raw_sql(f"""
    select distinct dlycaldt, vwretd
    from crsp_m_stock.wrds_dailyindexret_query
    where dlycaldt between '{crsp_begdate}' and '{crsp_enddate}'
    """, date_cols=['dlycaldt'])'''),
    (14, "ds = pd.merge(dsf, dsi, how='left', on=['date'])", "ds = pd.merge(dsf, dsi, how='left', on=['dlycaldt'])"),
    (14, "ds['exret'] = ds.ret - ds.vwretd", "ds['exret'] = ds.dlyret - ds.vwretd"),
    (14, "crsprets = crsprets.loc[(crsprets.date<=crsprets.ub_date) & (crsprets.date>=crsprets.lb_date)]",
         "crsprets = crsprets.loc[(crsprets.dlycaldt<=crsprets.ub_date)\n"
         "                        & (crsprets.dlycaldt>=crsprets.lb_date)]"),
    # ---- block 15
    (15, "temp = crsprets.sort_values(by=['permno', 'rdq1', 'date'])",
         "temp = crsprets.sort_values(by=['permno', 'rdq1', 'dlycaldt'])"),
    (15, "temp = temp.loc[(temp.rdq1<=temp.date) & (temp.date<=temp.leadrdq1)]",
         "temp = temp.loc[(temp.rdq1<=temp.dlycaldt) & (temp.dlycaldt<=temp.leadrdq1)]"),
]
for b, old, new in EDITS:
    assert old in blocks[b], f"block {b}: {old[:70]!r}"
    blocks[b] = blocks[b].replace(old, new)

# ---- block 17: Plotly chart in the site style -------------------------------------------
blocks[17] = '''# Plotting the output
# SUE quintiles on a diverging scale: most negative surprise (red) to most positive (blue)

QUINTILES = [('sueport1', 'sue1: Most Negative SUE Port', '#b8302f'),
             ('sueport2', 'sue2', '#ec8d8c'),
             ('sueport3', 'sue3', '#8a8984'),
             ('sueport4', 'sue4', '#6da7ec'),
             ('sueport5', 'sue5: Most Positive SUE Port', '#1c5cab')]

fig = go.Figure()
for col, label, color in QUINTILES:
    fig.add_trace(go.Scatter(x=peadsue3port['ncount'], y=peadsue3port[col],
                             name=label, mode='lines', line=dict(color=color, width=2),
                             hovertemplate='%{y:+.2%}<extra>' + label + '</extra>'))
    last = peadsue3port.iloc[-1]
    fig.add_annotation(x=last['ncount'], y=last[col], xanchor='left', xshift=8,
                       text=f"<b>{label.split(':')[0]}</b> {last[col]:+.1%}",
                       showarrow=False, font=dict(size=12, color='#0b0b0b'))
fig.add_hline(y=0, line=dict(color='#8a8984', width=1, dash='dot'))
fig.update_layout(
    title=dict(text='CARs following EAD for Analyst-based SUE portfolios'
                    '<br><sup style="color:#52514e">Sample: S&P 500 members, '
                    f'fiscal quarters {begdate[-4:]}–{enddate[-4:]}<br>'
                    'Value-weighted excess returns over the CRSP '
                    'value-weighted index</sup>',
               x=0, xanchor='left'),
    template='plotly_white', height=560, margin=dict(l=70, r=110, t=100, b=150),
    font=dict(family='Inter, system-ui, sans-serif', size=13, color='#0b0b0b'),
    paper_bgcolor='#fcfcfb', plot_bgcolor='#fcfcfb', hovermode='x unified',
    legend=dict(orientation='h', x=0, y=-0.2, yanchor='top'),
    xaxis=dict(title='Event time, t=0 is Earnings Announcement Date', showgrid=False,
               ticks='outside', tickcolor='#c3c2b7', linecolor='#c3c2b7',
               range=[0, peadsue3port['ncount'].max()]),
    yaxis=dict(title='Cumulative Value-Weighted Excess Returns', tickformat='.0%',
               gridcolor='#ecebe7', zeroline=False),
)
fig.show()'''

# ---- formatting: black (single quotes kept), so every line fits the site's code box ---------
import subprocess  # noqa: E402

UVX = os.path.expanduser("~/.local/bin/uvx")


def black(src):
    out = subprocess.run([UVX, "black", "-q", "--line-length", "75", "--skip-string-normalization", "-"],
                         input=src, capture_output=True, text=True, check=True)
    return out.stdout.rstrip("\n")


import textwrap  # noqa: E402


def reindent_sql(src):
    """SQL inside conn.raw_sql(\"\"\"...\"\"\") re-indented to 4 spaces, as on the other pages."""
    def fix(m):
        sql = textwrap.dedent(m.group(2).strip("\n")).strip("\n")
        sql = "\n".join(("    " + l) if l.strip() else "" for l in sql.splitlines())
        return f'{m.group(1)}"""\n{sql}\n    """'
    return re.sub(r'(raw_sql\(\s*f?)"""(.*?)"""', fix, src, flags=re.S)


# long SQL select lists and comments split at natural points (applied after black)
LINE_WRAP = [
    ("    select ticker, anndats as repdats, value as act, pends as fpedats, pdicity",
     "    select ticker, anndats as repdats, value as act,\n           pends as fpedats, pdicity"),
    ("    select gvkey, fyearq, fqtr, conm, datadate, rdq, epsfxq, epspxq, cshoq, prccq,\n"
     "    ajexq, spiq, cshoq, cshprq, cshfdq, saleq, atq, fyr, datafqtr, cshoq*prccq as mcap",
     "    select gvkey, fyearq, fqtr, conm, datadate, rdq, epsfxq, epspxq,\n"
     "           cshoq, prccq, ajexq, spiq, cshoq, cshprq, cshfdq, saleq,\n"
     "           atq, fyr, datafqtr, cshoq*prccq as mcap"),
    ("    where consol='C' and popsrc='D' and indfmt='INDL' and datafmt='STD'",
     "    where consol='C' and popsrc='D'\n    and indfmt='INDL' and datafmt='STD'"),
    ("# Update Note: this version uses CRSP data to extract S&P500 Index constituents,",
     "# Update Note: this version uses CRSP data to extract S&P500 Index\n# constituents,"),
    ("# Group by company fpedats estimator analys then pick the last record in the group",
     "# Group by company fpedats estimator analys then pick the last record\n# in the group"),
    ("# Compute the median forecast based on estimates in the 90 days prior to the EAD",
     "# Compute the median forecast based on estimates in the 90 days prior\n# to the EAD"),
    ("# Form portfolios on Compustat-based SUEs (=sue1 or =sue2) or IBES-based SUE (=sue3)",
     "# Form portfolios on Compustat-based SUEs (=sue1 or =sue2)\n# or IBES-based SUE (=sue3)"),
    ("# SUE quintiles on a diverging scale: most negative surprise (red) to most positive (blue)",
     "# SUE quintiles on a diverging scale:\n# most negative surprise (red) to most positive (blue)"),
    ("    and permno in (select distinct permno from crsp_m_indexes.msp500list_v2)",
     "    and permno in (select distinct permno\n                   from crsp_m_indexes.msp500list_v2)"),
]

for b in blocks:
    blocks[b] = black(reindent_sql(blocks[b]))
used = set()
for b in blocks:
    for k, (o, n) in enumerate(LINE_WRAP):
        if o in blocks[b]:
            blocks[b] = blocks[b].replace(o, n)
            used.add(k)
assert used == set(range(len(LINE_WRAP))), [LINE_WRAP[k][0][:60] for k in set(range(len(LINE_WRAP))) - used]

# ---- assemble ------------------------------------------------------------------------------
cells = []
bi = 0
for seg in segments:
    if seg.startswith("```python"):
        bi += 1
        cells.append(nbf.v4.new_code_cell(blocks[bi]))
        continue
    text = re.sub(r'<div class="btn-row">.*?</div>\n*', "", seg, flags=re.S)       # legacy "Full Code" link
    text = re.sub(r"!\[\]\(\.\./images/data-crunching_pead/\d+\.png\)\n*", "", text)  # chart now produced by code
    text = text.replace("run the[ICLINK python code]", "run the [ICLINK python code]")
    if text.strip():
        cells.append(nbf.v4.new_markdown_cell(text.strip()))

too_long = [(i, l) for i, c in enumerate(cells) if c.cell_type == "code" for l in c.source.splitlines() if len(l) > 75]

nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, DEST)
print(f"wrote {os.path.relpath(DEST, ROOT)}: {sum(c.cell_type == 'code' for c in cells)} code cells")
for i, l in too_long:
    print(f"  long line ({len(l)}): {l}")
