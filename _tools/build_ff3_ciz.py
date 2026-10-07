"""Build notebooks/ff3_crspCIZ.ipynb from Freda's original notebooks/originals/ff3_crspCIZ.ipynb
(the WRDS "Fama-French Factors (Python - CIZ Format)" notebook).

The code is kept as written, with only these changes:
  - cell 0: plotly imports, so the comparison charts match the Momentum page; "Updated" date
  - cells 6, 18: sample extended to June 2026 from the CRSP quarterly update
                 (crsp_q_stock.msf_v2, crsp_q_ccm.ccmxpf_linktable)
  - cell 23: `.copy()` on the June slice (silences pandas SettingWithCopyWarning)
  - cell 27: cast ff.factors_monthly smb/hml to float (WRDS now returns them as Decimal,
             which breaks stats.pearsonr)
  - cell 29: matplotlib comparison chart replaced by Plotly charts in the Momentum style
  - trailing empty cell dropped
"""
import os
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "notebooks", "originals", "ff3_crspCIZ.ipynb")
DEST = os.path.join(ROOT, "notebooks", "ff3_crspCIZ.ipynb")

nb = nbf.read(SRC, as_version=4)
cells = nb.cells


def replace(i, old, new):
    assert old in cells[i].source, f"cell {i}: {old!r} not found"
    cells[i].source = cells[i].source.replace(old, new)


replace(0, "import matplotlib.pyplot as plt\n",
        "import matplotlib.pyplot as plt\nimport plotly.graph_objects as go\nimport plotly.io as pio\n"
        "from plotly.subplots import make_subplots\n")
replace(0, "from scipy import stats", "from scipy import stats\n\npio.renderers.default = 'notebook_connected'")
# Sample extended to June 2026: CRSP quarterly update (the annual crsp library ends December 2025)
replace(6, "# sql similar to crspmerge macro\n",
        "# sql similar to crspmerge macro\n"
        "# CRSP quarterly update (crsp_q_stock) runs through June 2026; the annual crsp library ends December 2025\n")
replace(6, "from crsp.msf_v2 as a", "from crsp_q_stock.msf_v2 as a")
replace(6, "where a.mthcaldt between '01/01/1959' and '12/31/2022'",
        "where a.mthcaldt between '01/01/1959' and '06/30/2026'")
replace(18, "from crsp.ccmxpf_linktable", "from crsp_q_ccm.ccmxpf_linktable")
replace(0, "# Updated:                               #", "# Updated: October 2026                  #")
replace(23, "june=ccm1_jun[['permno','mthcaldt', 'jdate', 'bmport','szport','posbm','nonmissport']]",
        "june=ccm1_jun[['permno','mthcaldt', 'jdate', 'bmport','szport','posbm','nonmissport']].copy()")
replace(27, "_ff=_ff[['date','smb','hml']]",
        "_ff=_ff[['date','smb','hml']]\n_ff[['smb','hml']]=_ff[['smb','hml']].astype(float)")

assert cells[29].source.lstrip().startswith("plt.figure"), "cell 29 is not the comparison chart"
assert not cells[30].source.strip(), "cell 30 is not empty"

monthly_md = nbf.v4.new_markdown_cell("""### Comparison charts

Monthly factor returns, replicated from CRSP CIZ (blue) against the Ken French data library factors on
WRDS (orange). Hover over the chart for both returns in a given month; drag across a period to zoom in.""")

monthly_chart = nbf.v4.new_code_cell("""#################################
# Monthly Factor Returns        #
#################################
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.14,
                    subplot_titles=('SMB', 'HML'))
for row, (ff_col, w_col, name) in enumerate([('smb','WSMB','SMB'), ('hml','WHML','HML')], start=1):
    # Ken French drawn first, replicated on top, so differences show in both colors
    for col, label, color, width, opacity in [(ff_col, 'Ken French', '#eb6834', 1.6, 1.0),
                                              (w_col, 'Replicated (CRSP CIZ)', '#2a78d6', 1.2, 0.85)]:
        fig.add_trace(go.Scatter(x=_ffcomp.index, y=_ffcomp[col], name=label, mode='lines', opacity=opacity,
                                 line=dict(color=color, width=width), legendgroup=label, showlegend=(row == 1),
                                 hovertemplate='%{y:+.2%}<extra>' + f'{label}: {col}' + '</extra>'), row=row, col=1)
    fig.add_hline(y=0, line=dict(color='#8a8984', width=1), row=row, col=1)
    fig.update_yaxes(title_text=f'{name} monthly return', tickformat='.0%', gridcolor='#ecebe7',
                     zeroline=False, row=row, col=1)
fig.update_xaxes(showgrid=False, ticks='outside', tickcolor='#c3c2b7', linecolor='#c3c2b7',
                 range=[_ffcomp.index[0], _ffcomp.index[-1]])
fig.update_annotations(font=dict(size=14, color='#0b0b0b'), x=0, xanchor='left', yshift=6)
fig.update_layout(
    title=dict(text=f'Comparison of Results<br><sup style="color:#52514e">Monthly SMB and HML, replicated vs. Ken French, '
                    f'{_ffcomp.index[0]:%b %Y}–{_ffcomp.index[-1]:%b %Y}</sup>', x=0, xanchor='left'),
    template='plotly_white', height=760, margin=dict(l=80, r=40, t=100, b=90),
    font=dict(family='Inter, system-ui, sans-serif', size=13, color='#0b0b0b'),
    paper_bgcolor='#fcfcfb', plot_bgcolor='#fcfcfb', hovermode='x unified',
    legend=dict(orientation='h', x=0, y=-0.07, yanchor='top'),
)
fig.show()""")

chart_md = nbf.v4.new_markdown_cell("""Growth of $1 invested in each factor, replicated from CRSP CIZ (blue) against the Ken French data library
factors on WRDS (orange), on a log scale. Hover over a line for the month, the value of $1 and the two
monthly factor returns.""")

chart_style = nbf.v4.new_code_cell("""#################################
# Chart Style                   #
#################################
COLORS = {'ff': '#eb6834', 'w': '#2a78d6'}

def log_ticks(series):
    # $ ticks at 1-2-5 steps covering the plotted range
    lo, hi = min(s.min() for s in series), max(s.max() for s in series)
    steps = (1, 1.5, 2, 3, 4, 5, 7) if hi / lo < 20 else (1, 2, 5)   # finer steps for a narrow range
    vals = [m * 10**e for e in range(-2, 8) for m in steps]
    vals = [v for v in vals if lo * 0.9 <= v <= hi * 1.1]
    return dict(tickvals=vals, ticktext=[f'${v:,.0f}' if v >= 1 and v == int(v) else f'${v:g}' for v in vals])

def factor_chart(ff_col, w_col, name):
    df = _ffcomp[[ff_col, w_col]].dropna()
    growth = {c: (1 + df[c]).cumprod() for c in (w_col, ff_col)}
    corr = stats.pearsonr(_ffcomp70[ff_col], _ffcomp70[w_col])[0]
    labels = {w_col: f'Replicated {name} (CRSP CIZ)', ff_col: f'Ken French {name}'}
    colors = {w_col: COLORS['w'], ff_col: COLORS['ff']}

    fig = go.Figure()
    for c in (w_col, ff_col):
        fig.add_trace(go.Scatter(x=df.index, y=growth[c], name=labels[c], mode='lines',
                                 line=dict(color=colors[c], width=2), customdata=df[c],
                                 hovertemplate='$%{y:,.2f} (month: %{customdata:+.2%})<extra>' + labels[c] + '</extra>'))
        fig.add_annotation(x=df.index[-1], y=np.log10(growth[c].iloc[-1]),
                           text=f'<b>{labels[c].split(" (")[0]}</b><br>${growth[c].iloc[-1]:,.2f}',
                           showarrow=False, xanchor='left', xshift=8, align='left', font=dict(color='#0b0b0b'))
    fig.add_hline(y=1, line=dict(color='#8a8984', width=1, dash='dot'))
    fig.update_layout(
        title=dict(text=f'{name}: Replicated vs. Ken French<br><sup style="color:#52514e">'
                        f'{df.index[0]:%b %Y}–{df.index[-1]:%b %Y}; correlation of monthly returns since 1970: {corr:.3f}</sup>',
                   x=0, xanchor='left'),
        template='plotly_white', height=520, margin=dict(l=70, r=190, t=80, b=90),
        font=dict(family='Inter, system-ui, sans-serif', size=13, color='#0b0b0b'),
        paper_bgcolor='#fcfcfb', plot_bgcolor='#fcfcfb', hovermode='x unified',
        legend=dict(orientation='h', x=0, y=-0.12, yanchor='top'),
        xaxis=dict(showgrid=False, ticks='outside', tickcolor='#c3c2b7', linecolor='#c3c2b7',
                   range=[df.index[0], df.index[-1]]),
        yaxis=dict(type='log', title='Growth of $1 (log scale)', gridcolor='#ecebe7', zeroline=False,
                   **log_ticks(growth.values())),
    )
    return fig""")

smb_chart = nbf.v4.new_code_cell("""factor_chart('smb', 'WSMB', 'SMB').show()""")
hml_chart = nbf.v4.new_code_cell("""factor_chart('hml', 'WHML', 'HML').show()""")

nb.cells = cells[:29] + [monthly_md, monthly_chart, chart_md, chart_style, smb_chart, hml_chart]
nbf.write(nb, DEST)
print(f"wrote {os.path.relpath(DEST, ROOT)} ({len(nb.cells)} cells)")
