"""Build the European Short Position Data page (web-scraping/european-short-position-data.ipynb).

The scraping pipeline itself lives in Freda's private repo github.com/wonderfreda/eu236; the page
now shows the data it produces plus the Norway API download as a runnable example:

  notebooks/eu_short_norway.ipynb     the Norway example (code from eu236 Part 2, Section 1),
                                      executed; also the page's download
  _tools/eu_short_overview.ipynb      coverage table + chart from the latest combined file
                                      (outputs/final_all_country_<date>.csv in a local eu236
                                      clone), executed; its cells appear on the page with the
                                      code hidden, since readers don't have the file

Usage (Anaconda python):  python3 _tools/build_eu_short.py [--no-run]
"""
import os
import re
import subprocess
import sys
import nbformat as nbf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_page import direct_plotly, header, table_too_wide  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "notebooks", "originals", "european-short-position-data.qmd")
DEST = os.path.join(ROOT, "web-scraping", "european-short-position-data.ipynb")
NORWAY = os.path.join(ROOT, "notebooks", "eu_short_norway.ipynb")
OVERVIEW = os.path.join(ROOT, "_tools", "eu_short_overview.ipynb")  # not published: local data path
EU236 = os.path.expanduser("~/wrds-rd-work/eu236")
DATA = os.path.join(EU236, "outputs", "final_all_country_20260928.csv")
UPDATE = "September 28, 2026"
PYTHON = os.path.expanduser("~/opt/anaconda3/bin/python")

body = open(PAGE).read().split("---", 2)[2]


def between(start, end):
    i = body.index(start)
    return body[i:body.index(end, i)].strip()


# Freda's prose, verbatim
BACKGROUND = between("## policy Background", "## code")
assert "Update: May 2024" in BACKGROUND
BACKGROUND = BACKGROUND.replace("Update: May 2024", "Update: October 2026")  # per Freda, 2026-10
NORWAY_INTRO = between("Norwegian Finanstilsynet", "```python")
ACTIVE_POSITIONS = between("The field activePositions", "![](")
EXAMPLE = between("For instance, below is the content", "```python\ndfValid")
DUPLICATES = between("Last step is to remove the redundant rows", "```python\nlongDf = longDf.drop")

# ---- Norway example: code from eu236_part2_clean_file_2026.ipynb, Section 1 -------------------
NORWAY_CELLS = [
    ("md", "# Norway Short Positions from the Finanstilsynet API\n\n"
           "Qingyi (Freda) Song Drechsler"),
    ("md", NORWAY_INTRO),
    ("code", '''# import packages
import json

import certifi
import pandas as pd
import urllib3'''),
    ("code", '''http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED',
                           ca_certs=certifi.where())
url = "https://ssr.finanstilsynet.no/api/v2/instruments"
r = http.request('GET', url)
assert r.status == 200, f"Norway API returned status {r.status}"

data = json.loads(r.data.decode('utf-8'))
df = pd.json_normalize(data, 'events', ["isin", "issuerName"],
                       max_level=0)
dfValid = df.loc[df.shares != 0]
print(f"Norway: {df.shape[0]} raw records, "
      f"{dfValid.shape[0]} with a nonzero position")'''),
    ("code", "df.head()"),
    ("md", ACTIVE_POSITIONS),
    ("md", EXAMPLE),
    ("code", '''# parse out the positionHolder info from the activePositions column
dateLst, holderLst, shortPctLst = [], [], []
shareLst, isinLst, issuerLst = [], [], []

for i in range(dfValid.shape[0]):
    thisIsin = dfValid.iloc[i].isin.__self__.to_dict()['isin']
    thisIssuer = dfValid.iloc[i].issuerName
    for pos in dfValid.iloc[i].activePositions:
        holderLst.append(pos['positionHolder'])
        shortPctLst.append(pos['shortPercent'])
        dateLst.append(pos['date'])
        shareLst.append(pos['shares'])
        isinLst.append(thisIsin)
        issuerLst.append(thisIssuer)

longDf = pd.DataFrame({
    'position_date': dateLst, 'isin': isinLst, 'issuer': issuerLst,
    'position_holder': holderLst, 'net_short_position': shortPctLst,
    'NumPositions': shareLst,
})'''),
    ("md", DUPLICATES),
    ("code", '''# the API reports one row per date with possibly several position
# holders, and holders who didn't change position get repeated on every
# subsequent date - drop those duplicates
longDf = longDf.drop_duplicates()
longDf.shape'''),
    ("md", "And the final output for Norway looks like the following:"),
    ("code", "longDf.sort_values(['isin', 'position_holder', 'position_date']).head()"),
]

# ---- overview: coverage by country and a chart, from the combined file -----------------------
OVERVIEW_CELLS = [
    ("code", f'''import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

pio.renderers.default = 'notebook_connected'
eu = pd.read_csv({DATA!r}, low_memory=False, parse_dates=['position_date'])'''),
    ("code", '''# coverage by country
cov = (eu.groupby('country')
         .agg(disclosures=('position_date', 'size'), companies=('isin', 'nunique'),
              holders=('position_holder', 'nunique'),
              first=('position_date', 'min'), last=('position_date', 'max'))
         .sort_values('disclosures', ascending=False))
total = pd.DataFrame({'disclosures': [len(eu)], 'companies': [eu['isin'].nunique()],
                      'holders': [eu.position_holder.nunique()],
                      'first': [eu.position_date.min()], 'last': [eu.position_date.max()]},
                     index=['All countries'])
cov = pd.concat([cov, total])
out = pd.DataFrame({
    'Disclosures': cov.disclosures.map('{:,}'.format),
    'Companies (ISINs)': cov.companies.map('{:,}'.format),
    'Position holders': cov.holders.map('{:,}'.format),
    'First position date': cov['first'].dt.strftime('%Y-%m-%d'),
    'Last position date': cov['last'].dt.strftime('%Y-%m-%d'),
}, index=cov.index.rename('Country'))
out'''),
    ("code", '''# companies with a disclosed position each month: top 4 countries + the rest
eu['month'] = eu.position_date.dt.to_period('M').dt.to_timestamp()
# Nov 2012 (regulation in force) to Jun 2026 (UK and Denmark files end in July)
m = eu.loc[(eu.month >= '2012-11-01') & (eu.month <= '2026-06-01')]
by = m.drop_duplicates(['country', 'month', 'isin']).groupby(['month', 'country']).size()
by = by.unstack(fill_value=0)
top = by.sum().sort_values(ascending=False).index[:4]
series = [(c, by[c], color) for c, color in
          zip(top, ['#2a78d6', '#eb6834', '#1baf7a', '#eda100'])]
series.append(('All other countries', by.drop(columns=top).sum(axis=1), '#8a8984'))

fig = go.Figure()
for name, s, color in series:
    fig.add_trace(go.Scatter(x=s.index, y=s, name=name, mode='lines',
                             line=dict(color=color, width=2),
                             hovertemplate='%{y:,}<extra>' + name + '</extra>'))
fig.update_layout(
    title=dict(text='Companies with a Disclosed Net Short Position, by Month'
                    '<br><sup style="color:#52514e">Distinct ISINs with at least one '
                    'position disclosure dated in the month, '
                    f'{by.index[0]:%b %Y}\\u2013{by.index[-1]:%b %Y}</sup>',
               x=0, xanchor='left'),
    template='plotly_white', height=500, margin=dict(l=60, r=30, t=90, b=110),
    font=dict(family='Inter, system-ui, sans-serif', size=13, color='#0b0b0b'),
    paper_bgcolor='#fcfcfb', plot_bgcolor='#fcfcfb', hovermode='x unified',
    legend=dict(orientation='h', x=0, y=-0.12, yanchor='top'),
    xaxis=dict(showgrid=False, ticks='outside', tickcolor='#c3c2b7',
               linecolor='#c3c2b7', hoverformat='%b %Y'),
    yaxis=dict(title='Companies', gridcolor='#ecebe7', zeroline=False, rangemode='tozero'),
)
fig.show()'''),
]

# ---- page text (DRAFT: new wording, for Freda's approval) -------------------------------------
DATA_TEXT = f"""## the data

The tables and chart below summarize the combined dataset as of the latest update ({UPDATE}): every
net short position disclosure published by the 19 regulators covered, with the position holder,
the company (issuer and ISIN), the net short position as a percentage of issued share capital,
and the position date."""
CHART_TEXT = """The chart counts the companies with at least one disclosure dated in each month, which is
comparable across countries; raw disclosure counts are not, since some regulators (Belgium until
2022, for example) repeat unchanged positions every day."""
PIPELINE_TEXT = """## the code

The code runs in two parts. Part 1 downloads each regulator's raw disclosure file, using Selenium
for sites that need clicking and plain HTTP requests where a file or API address is available.
Part 2 reads each country's file, standardizes the columns, runs validation checks, and appends
the new records to the previous update, since some regulators do not keep their full history
online.

The example below is the Norway download, which reads the regulator's API directly instead of
clicking through a website."""


def notebook(cells):
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_markdown_cell(s) if t == "md" else nbf.v4.new_code_cell(s) for t, s in cells]
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    return nb


if "--no-run" not in sys.argv:
    nbf.write(notebook(NORWAY_CELLS), NORWAY)
    nbf.write(notebook(OVERVIEW_CELLS), OVERVIEW)
    subprocess.run([PYTHON, os.path.join(ROOT, "_tools", "run_notebook.py"), NORWAY, OVERVIEW], check=True)

norway = nbf.read(NORWAY, as_version=4)
overview = nbf.read(OVERVIEW, as_version=4)
for c in overview.cells:
    c.source = "#| echo: false\n" + c.source
for c in norway.cells + overview.cells:
    if c.cell_type == "code" and any(table_too_wide(o["data"]["text/html"]) for o in c.get("outputs", [])
                                     if "<table" in o.get("data", {}).get("text/html", "")):
        c.source = "#| column: page\n" + c.source

meta = dict(src=NORWAY, intro="", meta=[
    ("Data", "Net short position disclosures under EU Regulation 236/2012, published by national "
             "regulators in the EU, the UK, Norway and Iceland"),
    ("Sample", f"19 countries, position dates through September 2026 (update of {UPDATE})"),
    ("Code", "Scraping and cleaning pipeline in two notebooks; the Norway download is the example below"),
    ("Author", "Qingyi (Freda) Song Drechsler"),
])
cells = [nbf.v4.new_raw_cell('---\ntitle: "European Short Position Data"\n---'),
         nbf.v4.new_markdown_cell(header(meta).replace("Download notebook (.ipynb)",
                                                       "Download Norway example (.ipynb)")),
         nbf.v4.new_markdown_cell(BACKGROUND),
         nbf.v4.new_markdown_cell(DATA_TEXT),
         overview.cells[1],
         nbf.v4.new_markdown_cell(CHART_TEXT),
         overview.cells[2],
         nbf.v4.new_markdown_cell(PIPELINE_TEXT)]
cells += [c for c in norway.cells[1:]]
cells[-len(norway.cells) + 1].source = "### example: Norway\n\n" + cells[-len(norway.cells) + 1].source
page = nbf.v4.new_notebook()
page.cells = cells
page.metadata = norway.metadata
direct_plotly(page)
nbf.write(page, DEST)
too_long = [l for c in norway.cells if c.cell_type == "code" for l in c.source.splitlines() if len(l) > 75]
print(f"wrote {os.path.relpath(DEST, ROOT)} ({len(cells)} cells)")
for l in too_long:
    print(f"  long line ({len(l)}): {l}")
