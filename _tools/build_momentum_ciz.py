"""Build notebooks/momentum_ciz.ipynb: Python translation of the WRDS SAS (CIZ format)
Jegadeesh-Titman (1993) momentum code, in the style of ff3_crspCIZ.ipynb."""
import os
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

cells = [
md("""# Jegadeesh and Titman (1993) Momentum Portfolios — CRSP CIZ Format

Python version of the WRDS research application *Momentum Strategies (CIZ format)*. Monthly returns come
from the CRSP Monthly Stock File in the new CIZ format (`msf_v2`). The sample is NYSE and AMEX common
stocks; portfolios are formed on past J-month returns and held for K months.

The sample runs through June 2026, using the CRSP monthly update on WRDS (`crsp_m_stock`); the annual
release in the `crsp` library ends in December 2025. The original 1965–1989 holding period is kept as a subsample to check the results against Jegadeesh and
Titman (1993) and the WRDS SAS code."""),

code("""################################################
# Jegadeesh & Titman (1993) Momentum Portfolio #
# CRSP CIZ Format                              #
# Qingyi (Freda) Song Drechsler                #
# Date: October 2026                           #
################################################

import pandas as pd
import numpy as np
import wrds
import plotly.graph_objects as go
import plotly.io as pio
from pandas.tseries.offsets import *
from scipy import stats

pio.renderers.default = 'notebook_connected'"""),

code("""conn = wrds.Connection()"""),

code("""######################
# Specifying Options #
######################
J = 6 # Formation Period Length: J can be between 3 to 12 months
K = 6 # Holding Period Length: K can be between 3 to 12 months

# Jegadeesh and Titman's Footnote 4 page 69: 1965-1989 are holding period dates
# Need 2 years of return history to form momentum portfolios that start in 1965
# Sample extended to June 2026; 1965-1989 is kept as the replication subsample
begdate = '01/01/1963'
enddate = '06/30/2026'

# CRSP monthly update: the annual library (crsp) ends December 2025,
# the monthly update (crsp_m_stock) covers the sample through June 2026
crsp_lib = 'crsp_m_stock'"""),

md("""## CRSP data

`msf_v2` carries the security attributes on every monthly record, so no separate names-file merge is
needed. The CIZ flags below replace the legacy `shrcd in (10,11)` and `exchcd in (1,2)` filters:
common shares of US-incorporated operating companies, primary listing on NYSE (`N`) or AMEX (`A`),
regular-way trading in active status."""),

code("""###################
# CRSP Block      #
###################
crsp_m = conn.raw_sql(f\"\"\"
                      select a.permno, a.mthcaldt, a.mthret,
                      a.issuertype, a.securitytype, a.securitysubtype, a.sharetype, a.usincflg,
                      a.primaryexch, a.conditionaltype, a.tradingstatusflg
                      from {crsp_lib}.msf_v2 as a
                      where a.mthcaldt between '{begdate}' and '{enddate}'
                      \"\"\", date_cols=['mthcaldt'])

crsp_m.shape"""),

code("""# Restriction on share type: common shares only
# and primary exchange: NYSE and AMEX securities only
crsp_m = crsp_m.loc[(crsp_m.sharetype=='NS') & (crsp_m.securitytype=='EQTY') &
                    (crsp_m.securitysubtype=='COM') & (crsp_m.usincflg=='Y') &
                    (crsp_m.issuertype.isin(['ACOR','CORP']))]

crsp_m = crsp_m.loc[(crsp_m.primaryexch.isin(['N','A'])) & (crsp_m.conditionaltype=='RW') &
                    (crsp_m.tradingstatusflg=='A')]

crsp_m = crsp_m[['permno','mthcaldt','mthret']].sort_values(['permno','mthcaldt']).reset_index(drop=True)
crsp_m['mthret'] = crsp_m['mthret'].astype(float)
crsp_m['permno'] = crsp_m['permno'].astype(int)

crsp_m.shape"""),

md("""## Formation-period returns

Cumulative return over the past J months, computed over each stock's consecutive monthly records:
the rolling product of (1 + return) minus one. As in the SAS `proc expand ... transformout=(movprod &J -1
trimleft &J)`, missing returns are skipped inside the window and each stock's first J records are set
to missing."""),

code("""#######################################################
# Create Momentum Portfolio                           #
# Measures Based on Past (J) Month Compounded Returns #
#######################################################

umd = crsp_m.copy()
umd['gross'] = 1 + umd['mthret']
umd['cum_return'] = umd.groupby('permno')['gross']\\
    .transform(lambda x: x.rolling(J, min_periods=1).apply(np.nanprod, raw=True)) - 1

# a window with no non-missing return has no cumulative return
_nret = umd.groupby('permno')['mthret'].transform(lambda x: x.rolling(J, min_periods=1).count())
umd.loc[_nret == 0, 'cum_return'] = np.nan

# trimleft J: the first J records of each permno are set to missing
umd['obs'] = umd.groupby('permno').cumcount() + 1
umd.loc[umd['obs'] <= J, 'cum_return'] = np.nan
umd = umd[['permno','mthcaldt','cum_return']]"""),

md("""## Portfolio formation

Ranks follow SAS `proc rank groups=10`: within each month, `floor(rank × 10 / (n + 1))` using
average ranks for ties, then shifted to run 1 (losers) to 10 (winners). Stocks without a formation
return are dropped. The holding period starts the month after formation (`HDATE1`) and ends K months
later (`HDATE2`)."""),

code("""########################################
# Formation of 10 Momentum Portfolios  #
########################################

umd = umd.dropna(subset=['cum_return'])
_rank = umd.groupby('mthcaldt')['cum_return'].rank(method='average')
_n = umd.groupby('mthcaldt')['cum_return'].transform('count')
umd['momr'] = np.floor(_rank*10/(_n+1)).astype(int) + 1

# 1 - the lowest momentum group: Losers
# 10 - the highest momentum group: Winners
umd['form_date'] = umd['mthcaldt']
umd['hdate1'] = umd['mthcaldt'] + MonthBegin(1)
umd['hdate2'] = umd['mthcaldt'] + MonthEnd(0) + MonthEnd(K)
umd = umd[['permno','form_date','momr','hdate1','hdate2']]\\
    .drop_duplicates(subset=['permno','form_date'])

umd.momr.value_counts().sort_index()"""),

md("""`hdate2` reproduces SAS `intnx("MONTH", mthcaldt, K, "E")`: the end of the calendar month K months
after formation. CIZ `mthcaldt` is the last *trading* day of the month, so the month-end anchor matters."""),

code("""# Check hdate1/hdate2 against intnx: first day of the next month, end of the K-th month after formation
assert (umd['hdate1'].dt.to_period('M') - umd['form_date'].dt.to_period('M')).apply(lambda x: x.n).eq(1).all()
assert (umd['hdate2'].dt.to_period('M') - umd['form_date'].dt.to_period('M')).apply(lambda x: x.n).eq(K).all()
assert umd['hdate2'].dt.is_month_end.all() and (umd['hdate1'].dt.day == 1).all()

#############################################
# Holding Period Returns                    #
#############################################
# hdate1<=mthcaldt<=hdate2 covers the K calendar months after formation.
# Expand each formation record into its K holding months and join on permno-month,
# instead of merging every formation record with every return of the same permno.
hold = umd.loc[umd.index.repeat(K)].copy()
hold['hmonth'] = hold['form_date'].dt.to_period('M') + hold.groupby(level=0).cumcount().add(1).values

_ret = crsp_m.assign(hmonth=crsp_m['mthcaldt'].dt.to_period('M'))
port = pd.merge(hold, _ret, on=['permno','hmonth'], how='inner')
port = port[(port['hdate1']<=port['mthcaldt']) & (port['mthcaldt']<=port['hdate2'])]
port = port[['momr','form_date','permno','mthcaldt','mthret']]\\
    .drop_duplicates(subset=['mthcaldt','momr','form_date','permno'])

port.shape"""),

md("""## Equally-weighted portfolio returns

Every month, each momentum decile holds K overlapping sub-portfolios, one per formation month. Returns are
averaged within each sub-portfolio, then across sub-portfolios. The first two years (1963–1964) are
formation history only and are excluded."""),

code("""##############################################
# Equally-Weighted Average Monthly Returns   #
##############################################

# Every date, each MOM group has J portfolios identified by formation date
umd3 = port.groupby(['mthcaldt','momr','form_date'])['mthret'].mean().reset_index()

# Skip first two years of the sample
start_yr = pd.to_datetime(begdate).year + 2
umd3 = umd3[umd3['mthcaldt'].dt.year >= start_yr]

# Create one return series per MOM group every month
ewretdat = umd3.groupby(['mthcaldt','momr'])['mthret'].agg(ewret='mean', ewretstd='std').reset_index()

#######################################
# Jegadeesh and Titman (1993) Table 1 #
#######################################
def tstats(x):
    t, p = stats.ttest_1samp(x.dropna(), 0.0)
    return pd.Series({'n': x.count(), 'mean': x.mean(), 't-stat': t, 'p-value': p})

mom_table = ewretdat.groupby('momr')['ewret'].apply(tstats).unstack()
mom_table['n'] = mom_table['n'].astype(int)
mom_table.style.format({'mean':'{:.2%}', 't-stat':'{:.2f}', 'p-value':'{:.4f}'})"""),

md("""## Long–short portfolio

Full sample, January 1965 to June 2026."""),

code("""#################################
# Long-Short Portfolio Returns  #
#################################

# Transpose portfolio layout to have columns as portfolio returns
ewretdat2 = ewretdat.pivot(index='mthcaldt', columns='momr', values='ewret')
ewretdat2 = ewretdat2.add_prefix('port')
ewretdat2 = ewretdat2.rename(columns={'port1':'losers', 'port10':'winners'})
ewretdat2['long_short'] = ewretdat2['winners'] - ewretdat2['losers']

# Compute Long-Short Portfolio Cumulative Returns
ewretdat3 = ewretdat2.copy()
ewretdat3['cumret_winners'] = (1+ewretdat3['winners']).cumprod()-1
ewretdat3['cumret_losers'] = (1+ewretdat3['losers']).cumprod()-1
ewretdat3['cumret_long_short'] = (1+ewretdat3['long_short']).cumprod()-1

#################################
# Portfolio Summary Statistics  #
#################################
mom_output = ewretdat3[['winners','losers','long_short']].apply(tstats).T
mom_output['n'] = mom_output['n'].astype(int)
mom_output.style.format({'mean':'{:.2%}', 't-stat':'{:.2f}', 'p-value':'{:.4f}'})"""),

md("""## Comparison with published results

Restricting the holding months to 1965–1989 reproduces the original sample. For J = 6 and K = 6, the WRDS
SAS (CIZ format) code reports winners 1.71% (t = 4.22), losers 0.80% (t = 1.59) and long–short 0.91%
(t = 3.01). Jegadeesh and Titman (1993, Table 1) report 1.74% (4.33), 0.79% (1.56) and 0.95% (3.07)."""),

code("""jt_sample = ewretdat3.loc['1965-01-01':'1989-12-31', ['winners','losers','long_short']]
jt_output = jt_sample.apply(tstats).T

published = pd.DataFrame({'SAS CIZ mean': [0.0171, 0.0080, 0.0091], 'SAS CIZ t': [4.22, 1.59, 3.01],
                          'JT (1993) mean': [0.0174, 0.0079, 0.0095], 'JT (1993) t': [4.33, 1.56, 3.07]},
                         index=['winners','losers','long_short'])
comparison = pd.concat([jt_output[['mean','t-stat']].rename(columns={'mean':'Python mean','t-stat':'Python t'}),
                        published], axis=1)
comparison.style.format({c:'{:.2%}' for c in comparison.columns if 'mean' in c} |
                        {c:'{:.2f}' for c in comparison.columns if c.endswith(' t')})"""),

md("""## Cumulative returns

Growth of $1 invested in January 1965, on a log scale so that equal vertical distances are equal percentage
changes across six decades. Hover over a line for the month, the value of $1 and that month's return."""),

code("""#################################
# Chart Style                   #
#################################
COLORS = {'winners': '#2a78d6', 'losers': '#eb6834', 'long_short': '#2a78d6'}
LABELS = {'winners': 'Winners (decile 10)', 'losers': 'Losers (decile 1)', 'long_short': 'Winners minus losers'}

def log_ticks(cols):
    # $ ticks at 1-2-5 steps covering the plotted range
    growth = 1 + ewretdat3[['cumret_' + c for c in cols]]
    lo, hi = growth.min().min(), growth.max().max()
    vals = [m * 10**e for e in range(-2, 8) for m in (1, 2, 5)]
    vals = [v for v in vals if lo / 2 <= v <= hi * 2]
    return dict(tickvals=vals, ticktext=[f'${v:,.0f}' if v >= 1 else f'${v:g}' for v in vals])

def base_layout(title, subtitle, cols):
    return dict(
        title=dict(text=f'{title}<br><sup style="color:#52514e">{subtitle}</sup>', x=0, xanchor='left'),
        template='plotly_white', height=480, margin=dict(l=70, r=150, t=80, b=50),
        font=dict(family='Inter, system-ui, sans-serif', size=13, color='#0b0b0b'),
        paper_bgcolor='#fcfcfb', plot_bgcolor='#fcfcfb', hovermode='x unified',
        xaxis=dict(showgrid=False, ticks='outside', tickcolor='#c3c2b7', linecolor='#c3c2b7',
                   range=[ewretdat3.index[0], ewretdat3.index[-1]]),
        yaxis=dict(type='log', title='Growth of $1 (log scale)', gridcolor='#ecebe7', zeroline=False,
                   **log_ticks(cols)),
    )

def growth_trace(col, showlegend=True):
    growth = 1 + ewretdat3['cumret_' + col]
    return go.Scatter(x=ewretdat3.index, y=growth, name=LABELS[col], mode='lines',
                      line=dict(color=COLORS[col], width=2), showlegend=showlegend,
                      customdata=ewretdat3[col],
                      hovertemplate='$%{y:,.2f} (month: %{customdata:+.1%})<extra>' + LABELS[col] + '</extra>')

def end_label(fig, col):
    last = ewretdat3.index[-1]
    growth = 1 + ewretdat3['cumret_' + col].iloc[-1]
    fig.add_annotation(x=last, y=np.log10(growth), text=f'<b>{LABELS[col].split(" (")[0]}</b><br>${growth:,.0f}',
                       showarrow=False, xanchor='left', xshift=8, align='left', font=dict(color='#0b0b0b'))"""),

code("""fig = go.Figure([growth_trace('winners'), growth_trace('losers')])
fig.update_layout(**base_layout('Cumulative Momentum Portfolio Returns',
                                f'Jegadeesh–Titman J={J}, K={K}; NYSE and AMEX common stocks, equally weighted, Jan 1965–{ewretdat3.index[-1]:%b %Y}',
                                ['winners','losers']))
fig.update_layout(height=520, margin=dict(b=90), legend=dict(orientation='h', x=0, y=-0.12, yanchor='top'))
end_label(fig, 'winners'); end_label(fig, 'losers')
fig.show()"""),

code("""fig = go.Figure([growth_trace('long_short', showlegend=False)])
fig.add_hline(y=1, line=dict(color='#8a8984', width=1, dash='dot'))
fig.update_layout(**base_layout('Performance of Long/Short Momentum Strategy',
                                f'Long winners, short losers; J={J}, K={K}, Jan 1965–{ewretdat3.index[-1]:%b %Y}',
                                ['long_short']))
end_label(fig, 'long_short')
fig.show()"""),
]

nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
os.makedirs(os.path.join(ROOT, "notebooks"), exist_ok=True)
nbf.write(nb, os.path.join(ROOT, "notebooks", "momentum_ciz.ipynb"))
print("wrote notebooks/momentum_ciz.ipynb")
