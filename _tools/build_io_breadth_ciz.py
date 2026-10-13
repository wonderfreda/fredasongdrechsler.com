"""Build notebooks/io_breadth_ciz.ipynb from the legacy Ownership Breadth page
(kept in notebooks/originals/io_breadth.qmd).

Freda's prose and code are kept. Changes (user-approved):
  - CRSP CIZ: monthly prices, shares and share adjustment factor from crsp_m_stock.msf_v2 with the
    CIZ common-stock filter (replaces msf + msenames, shrcd 10/11); 13F CUSIP -> PERMNO map from
    stksecurityinfohist (historical cusip, replaces msenames.ncusip); cfacpr/cfacshr become
    mthcumfacpr/mthcumfacshr.
  - Sample: 13F report dates Mar 1980 - Dec 2025 (Q1 2026 on WRDS lacks Vanguard's holdings); CRSP
    aligned to the same end date, since stocks without 13F data are kept by a right join.
  - tfn.s34type3 now has ~130 million rows: Steps 3-5 are wrapped in functions (code unchanged) and
    run one report year at a time; the security-level measures are stacked before Step 6.
  - groupby(...)['a','b'] -> groupby(...)[['a','b']] (required by pandas 2); .copy() on slices that
    are modified (SettingWithCopyWarning).
  - Charts in Plotly in the site style; the size-quintile chart is labeled as mean IO ratio.
"""
import os
import re
import subprocess
import textwrap
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "notebooks", "originals", "io_breadth.qmd")
DEST = os.path.join(ROOT, "notebooks", "io_breadth_ciz.ipynb")
UVX = os.path.expanduser("~/.local/bin/uvx")

body = open(PAGE).read().split("---", 2)[2]
segments = re.split(r"(```python\n.*?```)", body, flags=re.S)
code_blocks = [s[len("```python\n"):-3].rstrip("\n") for s in segments if s.startswith("```python")]
assert len(code_blocks) == 10, len(code_blocks)
blocks = {i: "\n".join(l.rstrip() for l in b.splitlines()) for i, b in enumerate(code_blocks, start=1)}

# ---- block 1: header, imports -----------------------------------------------------------------
EDITS = [
    (1, "# Updated: June 2020                             #",
        "# Updated: June 2020                             #\n# Updated: October 2026, CRSP CIZ format         #"),
    (1, "import matplotlib.pyplot as plt", "import plotly.graph_objects as go\nimport plotly.io as pio\n\n"
                                         "pio.renderers.default = 'notebook_connected'"),
    # ---- block 2: CRSP block on msf_v2
    (2, "enddate = '12/31/2017'",
        "# 13F report dates through December 2025: on WRDS, Q1 2026 lacks\n"
        "# Vanguard's holdings (filing header only), which would understate\n"
        "# ownership. CRSP uses the same end date: Step 6 keeps stocks\n"
        "# without 13F data through a right join.\n"
        "enddate = '12/31/2025'"),
    (2, '''crsp_m = conn.raw_sql(f"""
                      select a.permno, a.date,
                      a.ret, a.vol, a.shrout, a.prc, a.cfacpr, a.cfacshr
                      from crsp.msf as a
                      left join crsp.msenames as b
                      on a.permno=b.permno
                      and b.namedt<=a.date
                      and a.date<=b.nameendt
                      where a.date between '{begdate}' and '{enddate}'
                      and b.shrcd between 10 and 11
                      """, date_cols=['date'])''',
        '''# CRSP CIZ format: msf_v2 carries the security attributes on each record;
# common stocks only (equivalent to legacy shrcd = 10 or 11)
crsp_m = conn.raw_sql(f"""
    select distinct permno, mthcaldt, mthret, mthvol, shrout, mthprc,
           mthcumfacpr, mthcumfacshr
    from crsp_m_stock.msf_v2
    where mthcaldt between '{begdate}' and '{enddate}'
    and sharetype='NS' and securitytype='EQTY' and securitysubtype='COM'
    and usincflg='Y' and issuertype in ('ACOR', 'CORP')
    """, date_cols=['mthcaldt'])'''),
    (2, "crsp_m['mdate']=crsp_m['date']+pd.offsets.MonthEnd(0)", "crsp_m['mdate']=crsp_m['mthcaldt']+pd.offsets.MonthEnd(0)"),
    (2, "crsp_m['qdate']=crsp_m['date']+pd.offsets.QuarterEnd(0)", "crsp_m['qdate']=crsp_m['mthcaldt']+pd.offsets.QuarterEnd(0)"),
    (2, "crsp_m['p']=crsp_m['prc'].abs()/crsp_m['cfacpr'] # price adjusted",
        "crsp_m['p']=crsp_m['mthprc'].abs()/crsp_m['mthcumfacpr'] # price adjusted"),
    (2, "crsp_m['tso']=crsp_m['shrout']*crsp_m['cfacshr']*1e3 # total shares out adjusted",
        "crsp_m['tso']=crsp_m['shrout']*crsp_m['mthcumfacshr']*1e3 # total shares out adjusted"),
    (2, "crsp_m = crsp_m[['permno','mdate','qdate','date','cfacshr', 'p', 'tso','me']]",
        "crsp_m = crsp_m[['permno','mdate','qdate','mthcaldt','mthcumfacshr', 'p', 'tso','me']]"),
    # ---- block 9: double brackets
    (9, "io_median = io_ts.groupby(['rdate'])['ior','ioc_hhi','io_missing'].median().reset_index()",
        "io_median = io_ts.groupby(['rdate'])[['ior','ioc_hhi','io_missing']].median().reset_index()"),
]
for b, old, new in EDITS:
    assert old in blocks[b], f"block {b}: {old[:70]!r}"
    blocks[b] = blocks[b].replace(old, new)

# ---- blocks 4-6: Steps 3-5 as functions (code unchanged inside), run year by year --------------
blocks[4] = '''######################################
# Step 3                             #
# Extract Holdings and Adjust Shares #
######################################

# Map 13F's historical cusip to CRSP's permno information
# (CRSP CIZ format: historical cusip from stksecurityinfohist)
crsp = conn.raw_sql("""
    select distinct permno, cusip
    from crsp_m_stock.stksecurityinfohist
    where cusip != ''
    """)

# The 13F holdings file has grown to over 100 million records, so Steps 3-5
# are written as functions and run one report year at a time (see below).
def extract_holdings(fst_vint):
    # holdings for the first-vintage reports in fst_vint only
    s34type3 = conn.raw_sql(f"""
        select fdate, mgrno, cusip, shares
        from tfn.s34type3
        where fdate between '{fst_vint.fdate.min():%Y-%m-%d}'
                        and '{fst_vint.fdate.max():%Y-%m-%d}'
        """, date_cols=['fdate'])

    holdings_v1 = pd.merge(fst_vint, s34type3, how='inner', on=['fdate','mgrno'] )

    holdings_v2 = pd.merge(holdings_v1, crsp, how='inner', on='cusip')
    holdings_v2 = holdings_v2.drop(['cusip'], axis=1)
    return holdings_v2'''

blocks[5] = '''######################################
# Step 4                             #
# Adjust Shares Using CRSP CFACSHR   #
# Align at Vintage Dates             #
######################################

# Sanity Checks for Duplicates - Ultimately, Should be 0 Duplicates
crsp_qend = crsp_qend.drop_duplicates(subset=['permno','qdate'])

def adjust_shares(holdings_v2):
    holdings = pd.merge(holdings_v2, crsp_qend[['qdate','permno','mthcumfacshr']], \\
                        how='inner', left_on=['permno','fdate'], right_on=['permno','qdate'])

    # Calculate Adjusted Shares
    holdings['shares_adj']=holdings['shares']*holdings['mthcumfacshr']
    holdings=holdings.drop(['shares','qdate','mthcumfacshr','fdate'], axis=1)

    # Sanity Checks for Duplicates - Ultimately, Should be 0 Duplicates
    holdings = holdings.drop_duplicates(subset=['permno','rdate','mgrno'])
    return holdings'''

blocks[6] = '''######################################
# Step 5                             #
# Calculate Institutional Measures   #
# At Security Level                  #
######################################

def io_measures(holdings):
    holdings = holdings[holdings['shares_adj']>0]

    # Number of Owners
    io_numowners = holdings.groupby(['permno','rdate'])['shares_adj'].count().reset_index()\\
    .rename(columns={'shares_adj':'numowners'})

    # Number of Institutions
    io_numinst = holdings.groupby(['permno','rdate'])['NumInst'].max().reset_index()\\
    .rename(columns={'NumInst':'numinst'})

    # New Old Institutions and Total Shares held by institutions
    io_total = holdings.groupby(['permno','rdate'])[['first_report','last_report','shares_adj']]\\
    .sum().reset_index()\\
    .rename(columns={'first_report':'newinst', 'last_report':'oldinst','shares_adj':'io_total'})

    # USS
    tmp = holdings[['permno','rdate','shares_adj']].copy()
    tmp['shares_adj2'] = tmp['shares_adj']**2
    io_uss = tmp.groupby(['permno','rdate'])['shares_adj2'].sum().reset_index()\\
    .rename(columns={'shares_adj2':'io_ss'})

    # combine various metrics together
    io_metrics = pd.merge(io_numowners, io_numinst, how='inner', on=['permno','rdate'])
    io_metrics = pd.merge(io_metrics, io_total, how='inner', on =['permno','rdate'])
    io_metrics = pd.merge(io_metrics, io_uss, how='inner', on = ['permno','rdate'])
    return io_metrics'''

RUN_LOOP = '''# Run Steps 3-5 one report year at a time and stack the security-level
# measures. Each (permno, rdate) group falls within a single report year,
# so the result is the same as processing all holdings at once.
io_metrics_list = []
for yr in sorted(fst_vint.rdate.dt.year.unique()):
    holdings_v2 = extract_holdings(fst_vint[fst_vint.rdate.dt.year == yr])
    holdings = adjust_shares(holdings_v2)
    io_metrics_list.append(io_measures(holdings))

io_metrics = pd.concat(io_metrics_list, ignore_index=True)
print(f'{len(io_metrics):,} security-quarter records, '
      f'{io_metrics.rdate.min():%b %Y} - {io_metrics.rdate.max():%b %Y}')'''

# ---- charts ----------------------------------------------------------------------------------
CHART_STATS = '''# Time series of IO statistics of US common stocks
STATS = [('ior', 'ior: median IO ratio', '#2a78d6'),
         ('io_missing', 'io_missing: share without 13F data', '#eb6834'),
         ('ioc_hhi', 'ioc_hhi: median ownership concentration', '#1baf7a'),
         ('io_g1', 'io_g1: share with IO ratio above 1', '#eda100')]

fig = go.Figure()
for col, label, color in STATS:
    fig.add_trace(go.Scatter(x=io_stats['rdate'], y=io_stats[col], name=label,
                             mode='lines', line=dict(color=color, width=2),
                             hovertemplate='%{y:.3f}<extra>' + col + '</extra>'))
fig.update_layout(
    title=dict(text='Time Series of IO Statistics of US Common Stocks'
                    '<br><sup style="color:#52514e">Median Statistics, '
                    f'{io_stats.rdate.min():%b %Y}\\u2013{io_stats.rdate.max():%b %Y}'
                    '</sup>', x=0, xanchor='left'),
    template='plotly_white', height=560, margin=dict(l=70, r=40, t=90, b=150),
    font=dict(family='Inter, system-ui, sans-serif', size=13, color='#0b0b0b'),
    paper_bgcolor='#fcfcfb', plot_bgcolor='#fcfcfb', hovermode='x unified',
    legend=dict(orientation='h', x=0, y=-0.18, yanchor='top'),
    xaxis=dict(title='Report Date', showgrid=False, ticks='outside',
               tickcolor='#c3c2b7', linecolor='#c3c2b7',
               range=[io_stats.rdate.min(), io_stats.rdate.max()]),
    yaxis=dict(gridcolor='#ecebe7', zeroline=False),
)
fig.show()'''

CHART_SIZE = '''# Plot Time Series of IO Ratio by Size Quintiles
# size quintiles on a sequential scale: small (light) to large (dark)
QUINTS = [('IOR 1 Small', '#86b6ef'), ('IOR 2', '#5598e7'), ('IOR 3', '#2a78d6'),
          ('IOR 4', '#1c5cab'), ('IOR 5 Large', '#104281')]

# end labels: nudge apart labels whose values are within 3 points
ends = {col: io_bucket_ts[col].dropna().iloc[-1] for col, _ in QUINTS}
shift = {col: 0 for col in ends}
order = sorted(ends, key=ends.get)
for lo, hi in zip(order, order[1:]):
    if ends[hi] - ends[lo] < 0.03:
        shift[lo] -= 7
        shift[hi] += 7

fig = go.Figure()
for col, color in QUINTS:
    fig.add_trace(go.Scatter(x=io_bucket_ts['rdate'], y=io_bucket_ts[col], name=col,
                             mode='lines', line=dict(color=color, width=2),
                             hovertemplate='%{y:.1%}<extra>' + col + '</extra>'))
    fig.add_annotation(x=io_bucket_ts['rdate'].iloc[-1], y=ends[col],
                       text=f'<b>{col.split()[1]}</b> {ends[col]:.0%}',
                       showarrow=False, xanchor='left', xshift=8, yshift=shift[col],
                       font=dict(size=12, color='#0b0b0b'))
fig.update_layout(
    title=dict(text='Time Series of IO Ratio - by Size Buckets'
                    '<br><sup style="color:#52514e">Mean IO ratio within each '
                    'market-cap quintile (censored at 100%), '
                    f'{io_bucket_ts.rdate.min():%b %Y}\\u2013'
                    f'{io_bucket_ts.rdate.max():%b %Y}'
                    '</sup>',
               x=0, xanchor='left'),
    template='plotly_white', height=560, margin=dict(l=70, r=90, t=90, b=150),
    font=dict(family='Inter, system-ui, sans-serif', size=13, color='#0b0b0b'),
    paper_bgcolor='#fcfcfb', plot_bgcolor='#fcfcfb', hovermode='x unified',
    legend=dict(orientation='h', x=0, y=-0.18, yanchor='top'),
    xaxis=dict(title='Report Date', showgrid=False, ticks='outside',
               tickcolor='#c3c2b7', linecolor='#c3c2b7',
               range=[io_bucket_ts.rdate.min(), io_bucket_ts.rdate.max()]),
    yaxis=dict(tickformat='.0%', gridcolor='#ecebe7', zeroline=False),
)
fig.show()'''

# block 10: keep the computation, replace the matplotlib plot with CHART_SIZE
cut = blocks[10].index("# Plot Time Series of IO Ratio by Size Quntiles")
blocks[10] = blocks[10][:cut].rstrip() + "\n\n" + CHART_SIZE


# ---- formatting ----------------------------------------------------------------------------
def reindent_sql(src):
    def fix(m):
        sql = textwrap.dedent(m.group(2).strip("\n")).strip("\n")
        ind = re.match(r"\s*", src[src.rfind("\n", 0, m.start()) + 1:]).group(0)
        sql = "\n".join((ind + "    " + l) if l.strip() else "" for l in sql.splitlines())
        return f'{m.group(1)}"""\n{sql}\n{ind}    """'
    return re.sub(r'(raw_sql\(\s*f?)"""(.*?)"""', fix, src, flags=re.S)


def black(src):
    out = subprocess.run([UVX, "black", "-q", "--line-length", "75", "--skip-string-normalization", "-"],
                         input=src, capture_output=True, text=True, check=True)
    return out.stdout.rstrip("\n")


for b in blocks:
    blocks[b] = black(reindent_sql(blocks[b]))
RUN_LOOP, CHART_STATS = black(RUN_LOOP), black(CHART_STATS)

# Freda's long comments split at natural points
LINE_WRAP = [
    ("# For each stock(permno), each quarter (qdate), find the last monthly date (mdate)",
     "# For each stock(permno), each quarter (qdate),\n# find the last monthly date (mdate)"),
    ("# Note: a right join is necessary to indentify common stocks with no 13F data",
     "# Note: a right join is necessary to indentify common stocks\n# with no 13F data"),
]
for o, n in LINE_WRAP:
    hits = [b for b in blocks if o in blocks[b]]
    assert hits, o
    for b in hits:
        blocks[b] = blocks[b].replace(o, n)

# ---- assemble -------------------------------------------------------------------------------
cells = []
bi = 0
for seg in segments:
    if seg.startswith("```python"):
        bi += 1
        cells.append(nbf.v4.new_code_cell(blocks[bi]))
        if bi == 6:
            cells.append(nbf.v4.new_code_cell(RUN_LOOP))
        continue
    text = re.sub(r'<div class="btn-row">.*?</div>\n*', "", seg, flags=re.S)       # legacy "Full Code" link
    parts = re.split(r"!\[\]\(\.\./images/data-crunching_io_breadth/(\d)\.png\)\n*", text)
    for k, part in enumerate(parts):
        if k % 2 == 0:
            if part.strip():
                cells.append(nbf.v4.new_markdown_cell(part.strip()))
        elif part == "1":
            cells.append(nbf.v4.new_code_cell(CHART_STATS))
        # image 2 is produced by block 10

too_long = [l for c in cells if c.cell_type == "code" for l in c.source.splitlines() if len(l) > 75]
nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, DEST)
print(f"wrote {os.path.relpath(DEST, ROOT)}: {sum(c.cell_type == 'code' for c in cells)} code cells")
for l in too_long:
    print(f"  long line ({len(l)}): {l}")
