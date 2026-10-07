"""Build notebooks/iclink_ciz.ipynb: Python version of the WRDS SAS macro ICLINK (CIZ format),
following the structure and conventions of Freda's legacy Python ICLINK (iclink_v2)."""
import os
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

cells = [
md("""# ICLINK: Link IBES and CRSP — CRSP CIZ Format

Python version of the WRDS SAS macro *ICLINK (CIZ format)*. It builds a link table between IBES TICKER and
CRSP PERMNO in two layers: first through CUSIPs, then through exchange tickers for the firms that remain
unmatched. Company-name similarity adds a layer of quality check, and each link gets a score from
0 (best) to 6.

CRSP identifiers come from the CIZ names file `stocknames_v2`, where the company name is `issuernm` and the
historical CUSIP is `cusip` (`comnam` and `ncusip` in the legacy `stocknames` file). The CRSP monthly
update on WRDS (`crsp_m_stock`) is used."""),

code("""#####################################
# ICLINK: Link CRSP and IBES        #
# CRSP CIZ Format                   #
# Qingyi (Freda) Song Drechsler     #
# Date: June 2019                   #
# Updated: October 2026             #
#####################################

# This program replicates the SAS macro ICLINK_CIZ
# to create a linking table between CRSP and IBES
# Output is a score reflecting the quality of the link
# Score = 0 (best link) to Score = 6 (worst link)
#
# More explanation on score system:
# - 0: BEST match: using (cusip, cusip dates and company names)
#          or (exchange ticker, company names and 6-digit cusip)
# - 1: Cusips and cusip dates match but company names do not match
# - 2: Cusips and company names match but cusip dates do not match
# - 3: Cusips match but cusip dates and company names do not match
# - 4: tickers and 6-digit cusips match but company names do not match
# - 5: tickers and company names match but 6-digit cusips do not match
# - 6: tickers match but company names and 6-digit cusips do not match

import wrds
import pandas as pd
import numpy as np
from rapidfuzz import fuzz, utils
import plotly.graph_objects as go
import plotly.io as pio

pio.renderers.default = 'notebook_connected'

# CRSP monthly update
crsp_lib = 'crsp_m_stock'

###################
# Connect to WRDS #
###################
conn=wrds.Connection()"""),

md("""## Step 1: Link by CUSIP

Company identifying information from IBES: CUSIP, TICKER, company name and the date range of each
CUSIP record."""),

code("""#########################
# Step 1: Link by CUSIP #
#########################

# 1.1 IBES: Get the list of IBES Tickers for US firms in IBES
_ibes1 = conn.raw_sql(\"\"\"
                      select ticker, cusip, cname, sdates from ibes.id
                      where usfirm=1 and cusip != ''
                      \"\"\", date_cols=['sdates'])

# Create first and last 'start dates' for a given cusip
# Use agg min and max to find the first and last date per group
# then rename to fdate and ldate respectively

_ibes1_date = _ibes1.groupby(['ticker','cusip']).sdates.agg(['min', 'max'])\\
.reset_index().rename(columns={'min':'fdate', 'max':'ldate'})

# merge fdate ldate back to _ibes1 data
_ibes2 = pd.merge(_ibes1, _ibes1_date,how='left', on =['ticker','cusip'])
_ibes2 = _ibes2.sort_values(by=['ticker','cusip','sdates'])

# keep only the most recent company name
# determined by having sdates = ldate
_ibes2 = _ibes2.loc[_ibes2.sdates == _ibes2.ldate].drop(['sdates'], axis=1)

_ibes2.shape"""),

md("""The same on the CRSP side: PERMNO, CUSIP, company name and date ranges, from the CIZ names file."""),

code("""# 1.2 CRSP: Get all permno-cusip combinations
_crsp1 = conn.raw_sql(f\"\"\"
                      select permno, cusip, issuernm, namedt, nameenddt
                      from {crsp_lib}.stocknames_v2
                      where cusip != ''
                      \"\"\", date_cols=['namedt', 'nameenddt'])
# first namedt
_crsp1_fnamedt = _crsp1.groupby(['permno','cusip']).namedt.min().reset_index()

# last nameenddt
_crsp1_lnameenddt = _crsp1.groupby(['permno','cusip']).nameenddt.max().reset_index()

# merge both
_crsp1_dtrange = pd.merge(_crsp1_fnamedt, _crsp1_lnameenddt, \\
                          on = ['permno','cusip'], how='inner')

# replace namedt and nameenddt with the version from the dtrange
_crsp1 = _crsp1.drop(['namedt'],axis=1).rename(columns={'nameenddt':'enddt'})
_crsp2 = pd.merge(_crsp1, _crsp1_dtrange, on =['permno','cusip'], how='inner')

# keep only most recent company name
_crsp2 = _crsp2.loc[_crsp2.enddt ==_crsp2.nameenddt].drop(['enddt'], axis=1)

_crsp2.shape"""),

md("""Link the two through matching CUSIPs. CUSIPs are not reused for different companies over time, so the
date ranges are used only in scoring."""),

code("""# 1.3 Create CUSIP Link Table

# Link by full cusip, company names and dates
_link1_1 = pd.merge(_ibes2, _crsp2, how='inner', on='cusip')\\
.sort_values(['ticker','permno','ldate'])

# Keep link with most recent company name
_link1_1_tmp = _link1_1.groupby(['ticker','permno']).ldate.max().reset_index()
_link1_2 = pd.merge(_link1_1, _link1_1_tmp, how='inner', on =['ticker', 'permno', 'ldate'])"""),

md("""To make sure that the matched pairs are indeed the same company, a company-name check is added on top.
The SAS macro uses the spelling distance `spedis`; here the name similarity comes from the
`token_set_ratio` of [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz), the maintained successor to
FuzzyWuzzy. With `processor=utils.default_process` (lowercase, punctuation stripped) it returns the same
scores as FuzzyWuzzy's `token_set_ratio`."""),

code("""# Calculate name matching ratio using RapidFuzz

# Note: fuzz ratio = 100 -> match perfectly
#       fuzz ratio = 0   -> do not match at all

# Comment: token_set_ratio is more flexible in matching the strings:
# fuzz.token_set_ratio('AMAZON.COM INC',  'AMAZON COM INC', processor=utils.default_process)
# returns value of 100

# fuzz.ratio('AMAZON.COM INC',  'AMAZON COM INC')
# returns value of 93

_link1_2['name_ratio'] = _link1_2.apply(lambda x: fuzz.token_set_ratio(x.issuernm, x.cname,
                                                                       processor=utils.default_process), axis=1)

# Note on parameters:
# The following parameters are chosen to mimic the SAS macro %iclink
# In %iclink, name_dist < 30 is assigned score = 0
# where name_dist=30 is roughly 90% percentile in total distribution
# and higher name_dist means more different names.
# In name_ratio, I mimic this by choosing 10% percentile as cutoff to assign
# score = 0

# 10% percentile of the company name distance
name_ratio_p10 = _link1_2.name_ratio.quantile(0.10)
name_ratio_p10"""),

md("""With `name_ratio` in place, the 10th percentile serves as the cutoff for a good name match. The function
`score1` assigns link scores from the name match and the overlap of the IBES and CRSP date ranges."""),

code("""# Function to assign score for companies matched by:
# full cusip and passing name_ratio
# or meeting date range requirement

def score1(row):
    if (row['fdate']<=row['nameenddt']) & (row['ldate']>=row['namedt']) & (row['name_ratio'] >= name_ratio_p10):
        score = 0
    elif (row['fdate']<=row['nameenddt']) & (row['ldate']>=row['namedt']):
        score = 1
    elif row['name_ratio'] >= name_ratio_p10:
        score = 2
    else:
        score = 3
    return score

# assign score
_link1_2['score']=_link1_2.apply(score1, axis=1)
_link1_2 = _link1_2[['ticker','permno','cname','issuernm','name_ratio','score']]
_link1_2 = _link1_2.drop_duplicates()

_link1_2.groupby(['score']).score.count()"""),

md("""## Step 2: Link by TICKER

For the IBES tickers not matched through CUSIP, the exchange ticker is the linking key. Exchange tickers are
reused over time, so the IBES and CRSP date ranges must overlap."""),

code("""##########################
# Step 2: Link by TICKER #
##########################

# Find links for the remaining unmatched cases using Exchange Ticker

# Identify remaining unmatched cases
_nomatch1 = pd.merge(_ibes2[['ticker']], _link1_2[['permno','ticker']], on='ticker', how='left')
_nomatch1 = _nomatch1.loc[_nomatch1.permno.isnull()].drop(['permno'], axis=1).drop_duplicates()

# Add IBES identifying information

ibesid = conn.raw_sql(\"\"\" select ticker, cname, oftic, sdates, cusip from ibes.id \"\"\", date_cols=['sdates'])
ibesid = ibesid.loc[ibesid.oftic.notna()]

_nomatch2 = pd.merge(_nomatch1, ibesid, how='inner', on=['ticker'])

# Create first and last 'start dates' for Exchange Tickers
# Label date range variables and keep only most recent company name

_nomatch3 = _nomatch2.groupby(['ticker', 'oftic']).sdates.agg(['min', 'max'])\\
.reset_index().rename(columns={'min':'fdate', 'max':'ldate'})

_nomatch3 = pd.merge(_nomatch2, _nomatch3, how='left', on=['ticker','oftic'])

_nomatch3 = _nomatch3.loc[_nomatch3.sdates == _nomatch3.ldate]

_nomatch3.shape"""),

md("""CRSP identifying information with exchange tickers. The CRSP ticker is renamed `crsp_ticker` and the
CRSP CUSIP `crsp_cusip`, to keep them apart from the IBES TICKER and CUSIP."""),

code("""# Get entire list of CRSP stocks with Exchange Ticker information

_crsp_n1 = conn.raw_sql(f\"\"\" select ticker, issuernm, permno, cusip, namedt, nameenddt
                            from {crsp_lib}.stocknames_v2 \"\"\", date_cols=['namedt', 'nameenddt'])

_crsp_n1 = _crsp_n1.loc[_crsp_n1.ticker.notna()].sort_values(by=['permno','ticker','namedt'])

# Arrange effective dates for link by Exchange Ticker

_crsp_n1_namedt = _crsp_n1.groupby(['permno','ticker']).namedt.min().reset_index()
_crsp_n1_nameenddt = _crsp_n1.groupby(['permno','ticker']).nameenddt.max().reset_index()

_crsp_n1_dt = pd.merge(_crsp_n1_namedt, _crsp_n1_nameenddt, how = 'inner', on=['permno','ticker'])

_crsp_n1 = _crsp_n1.rename(columns={'namedt': 'namedt_ind', 'nameenddt':'nameenddt_ind'})

_crsp_n2 = pd.merge(_crsp_n1, _crsp_n1_dt, how ='left', on = ['permno','ticker'])

_crsp_n2 = _crsp_n2.rename(columns={'ticker':'crsp_ticker', 'cusip':'crsp_cusip'})
_crsp_n2 = _crsp_n2.loc[_crsp_n2.nameenddt_ind == _crsp_n2.nameenddt].drop(['namedt_ind', 'nameenddt_ind'], axis=1)

_crsp_n2.shape"""),

md("""Merge the unmatched IBES tickers with CRSP on exchange ticker, then score each link with the 6-digit
CUSIP and the same name-match cutoff as in step 1."""),

code("""# Merge remaining unmatched cases using Exchange Ticker
# Note: Use ticker date ranges as exchange tickers are reused overtime

_link2_1 = pd.merge(_nomatch3, _crsp_n2, how='inner', left_on=['oftic'], right_on=['crsp_ticker'])
_link2_1 = _link2_1.loc[(_link2_1.ldate>=_link2_1.namedt) & (_link2_1.fdate<=_link2_1.nameenddt)]

# Score using company name using 6-digit CUSIP and company name spelling distance
_link2_1['name_ratio'] = _link2_1.apply(lambda x: fuzz.token_set_ratio(x.issuernm, x.cname,
                                                                       processor=utils.default_process), axis=1)

_link2_2 = _link2_1.copy()
_link2_2['cusip6'] = _link2_2['cusip'].str[:6]
_link2_2['crsp_cusip6'] = _link2_2['crsp_cusip'].str[:6]

# Score using company name using 6-digit CUSIP and company name spelling distance

def score2(row):
    if (row['cusip6']==row['crsp_cusip6']) & (row['name_ratio'] >= name_ratio_p10):
        score = 0
    elif (row['cusip6']==row['crsp_cusip6']):
        score = 4
    elif row['name_ratio'] >= name_ratio_p10:
        score = 5
    else:
        score = 6
    return score

# assign score
_link2_2['score']=_link2_2.apply(score2, axis=1)

# Some companies may have more than one TICKER-PERMNO link
# so re-sort and keep the case (PERMNO & Company name from CRSP)
# that gives the lowest score for each IBES TICKER

_link2_2 = _link2_2[['ticker','permno','cname','issuernm', 'name_ratio', 'score']].sort_values(by=['ticker','score'])
_link2_2_score = _link2_2.groupby(['ticker']).score.min().reset_index()

_link2_3 = pd.merge(_link2_2, _link2_2_score, how='inner', on=['ticker', 'score'])
_link2_3 = _link2_3[['ticker','permno','cname','issuernm','name_ratio','score']].drop_duplicates()

_link2_3.groupby(['score']).score.count()"""),

md("""## Step 3: Finalize links and scores

Combine the CUSIP and TICKER links. The link table is often used by other programs, so it is stored as a
static file for later use."""),

code("""#####################################
# Step 3: Finalize Links and Scores #
#####################################

iclink = pd.concat([_link1_2, _link2_3], ignore_index=True)
iclink = iclink.sort_values(by=['ticker','score','permno']).reset_index(drop=True)

# Storing iclink for other program usage
iclink.to_pickle('iclink.pkl')

print(f'{len(iclink):,} links, {iclink.ticker.nunique():,} IBES tickers, {iclink.permno.nunique():,} CRSP permnos')
iclink.head()"""),

md("""## Comparison with the WRDS link table

WRDS publishes its own IBES–CRSP link table, `wrdsapps_link_crsp_ibes.ibcrsphist`, built with a
history-based scoring scheme that is not comparable score by score. As a check on the links themselves:
the share of ICLINK's TICKER–PERMNO pairs that also appear in the WRDS table, by score."""),

code("""###################################
# Compare With WRDS Link Table    #
###################################
_wrds_link = conn.raw_sql(\"\"\" select distinct ticker, permno from wrdsapps_link_crsp_ibes.ibcrsphist
                              where permno is not null \"\"\")
_wrds_link['permno'] = _wrds_link['permno'].astype(int)
_wrds_link['in_wrds'] = 1

_check = pd.merge(iclink, _wrds_link, how='left', on=['ticker','permno'])
_check['in_wrds'] = _check['in_wrds'].fillna(0)

link_check = _check.groupby('score').agg(links=('ticker','count'), share_in_wrds=('in_wrds','mean'))
link_check.loc['all'] = [len(_check), _check['in_wrds'].mean()]
link_check['links'] = link_check['links'].astype(int)
link_check.style.format({'links':'{:,}', 'share_in_wrds':'{:.1%}'})"""),

md("""## Distribution of link scores and name matching

The distribution of link scores, and of `name_ratio`, give a sense of how well the two databases link.
Hover over a bar for the exact count."""),

code("""#################################
# Chart Style                   #
#################################
BLUE = '#2a78d6'

def base_layout(title, subtitle):
    return dict(
        title=dict(text=f'{title}<br><sup style="color:#52514e">{subtitle}</sup>', x=0, xanchor='left'),
        template='plotly_white', height=440, margin=dict(l=70, r=40, t=80, b=60),
        font=dict(family='Inter, system-ui, sans-serif', size=13, color='#0b0b0b'),
        paper_bgcolor='#fcfcfb', plot_bgcolor='#fcfcfb', bargap=0.25, showlegend=False,
        xaxis=dict(showgrid=False, ticks='outside', tickcolor='#c3c2b7', linecolor='#c3c2b7'),
        yaxis=dict(gridcolor='#ecebe7', zeroline=False),
    )"""),

code("""_score_n = iclink.groupby('score').size().reindex(range(7), fill_value=0)
_score_desc = {0: 'Best match', 1: 'CUSIP + dates', 2: 'CUSIP + name', 3: 'CUSIP only',
               4: 'Ticker + CUSIP6', 5: 'Ticker + name', 6: 'Ticker only'}

fig = go.Figure(go.Bar(x=_score_n.index, y=_score_n.values, marker=dict(color=BLUE),
                       text=[f'{v:,}' for v in _score_n.values], textposition='outside',
                       textfont=dict(color='#52514e', size=12),
                       customdata=[_score_desc[s] for s in _score_n.index],
                       hovertemplate='Score %{x}: %{customdata}<br>%{y:,} links<extra></extra>'))
fig.update_layout(**base_layout('Distribution of ICLINK Scores',
                                f'{len(iclink):,} IBES TICKER–CRSP PERMNO links; 0 = best, 6 = weakest'))
fig.update_xaxes(tickmode='array', tickvals=list(range(7)),
                 ticktext=[f'{s}<br><span style="font-size:11px;color:#52514e">{_score_desc[s]}</span>' for s in range(7)])
fig.update_yaxes(title_text='Number of links', range=[0, _score_n.max()*1.12])
fig.show()"""),

code("""fig = go.Figure(go.Histogram(x=iclink['name_ratio'], xbins=dict(start=0, end=102, size=2),
                             marker=dict(color=BLUE, line=dict(color='#fcfcfb', width=1)),
                             hovertemplate='name_ratio %{x}<br>%{y:,} links<extra></extra>'))
fig.add_vline(x=name_ratio_p10, line=dict(color='#52514e', width=1, dash='dot'))
fig.add_annotation(x=name_ratio_p10, y=1, yref='paper', yanchor='bottom', xanchor='right', showarrow=False,
                   text=f'name-match cutoff (10th percentile): {name_ratio_p10:.0f}',
                   font=dict(color='#52514e', size=12))
fig.update_layout(**base_layout('Distribution of Company Name Matching',
                                'RapidFuzz token_set_ratio between IBES and CRSP company names; 100 = identical'))
fig.update_layout(bargap=0)
fig.update_xaxes(title_text='name_ratio', range=[0, 102])
fig.update_yaxes(title_text='Number of links (log scale)', type='log',
                 tickvals=[1, 10, 100, 1000, 10000], ticktext=['1', '10', '100', '1,000', '10,000'])
fig.show()"""),
]

nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, os.path.join(ROOT, "notebooks", "iclink_ciz.ipynb"))
print("wrote notebooks/iclink_ciz.ipynb")
