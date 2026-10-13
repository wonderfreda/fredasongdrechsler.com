"""Build notebooks/exchange_rate.ipynb from the legacy Exchange Rate page
(kept in notebooks/originals/exchange-rate.qmd).

Freda's prose and code are kept; the screenshots become the cells that produce those outputs:
tables via .head()/.tail(), and the three exchange-rate charts in Plotly in the site style (the page
had no plotting code). matplotlib imports are replaced by plotly; code formatted with black.
"""
import os
import re
import subprocess
import textwrap
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "notebooks", "originals", "exchange-rate.qmd")
DEST = os.path.join(ROOT, "notebooks", "exchange_rate.ipynb")
UVX = os.path.expanduser("~/.local/bin/uvx")
IMG = "intro-to-python-for-fnce_exchange-rate"

body = open(PAGE).read().split("---", 2)[2]
segments = re.split(r"(```python\n.*?```)", body, flags=re.S)
blocks = [s[len("```python\n"):-3].rstrip("\n") for s in segments if s.startswith("```python")]
blocks = {i: "\n".join(l.rstrip() for l in b.splitlines()) for i, b in enumerate(blocks, start=1)}
assert len(blocks) == 6

old = "%matplotlib inline\nimport matplotlib.pyplot as plt"
assert old in blocks[1]
blocks[1] = blocks[1].replace(old, "import plotly.graph_objects as go\nimport plotly.io as pio\n\n"
                                   "pio.renderers.default = 'notebook_connected'")


def chart(x, y, title, source, color='#2a78d6'):
    return f'''# {title}
fig = go.Figure(go.Scatter(
    x={x}, y={y}, mode='lines', line=dict(color='{color}', width=2),
    hovertemplate='%{{x|%b %Y}}: %{{y:.4f}} CNY per USD<extra></extra>'))
fig.update_layout(
    title=dict(text='Exchange Rate - {source}'
                    '<br><sup style="color:#52514e">CNY per USD</sup>',
               x=0, xanchor='left'),
    template='plotly_white', height=440, showlegend=False,
    margin=dict(l=60, r=30, t=80, b=50),
    font=dict(family='Inter, system-ui, sans-serif', size=13, color='#0b0b0b'),
    paper_bgcolor='#fcfcfb', plot_bgcolor='#fcfcfb', hovermode='x',
    xaxis=dict(showgrid=False, ticks='outside', tickcolor='#c3c2b7',
               linecolor='#c3c2b7'),
    yaxis=dict(title='CNY per USD', gridcolor='#ecebe7', zeroline=False))
fig.show()'''


IMAGE_CELLS = {
    1: chart("cnyusd['datadate']", "cnyusd['cnyusd']", "Plot CNY per USD from Compustat Global", "Compustat"),
    2: "wsExRate.head()",
    3: chart("wsExRate['medate']", "wsExRate['localPerUSD']", "Plot CNY per USD from Worldscope", "Worldscope"),
    4: "dsfxcode.head()",
    5: "dsCNYUSD.tail()",
    6: chart("dsCNYUSD['exratedate']", "dsCNYUSD['midrate']", "Plot CNY per USD from Datastream (SPOT midrate)",
             "Datastream (SPOT)"),
}


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
IMAGE_CELLS = {k: black(v) for k, v in IMAGE_CELLS.items()}
LONG_COMMENT = "# create local currency per USD for comparison against Compustat Global output"
assert LONG_COMMENT in blocks[4]
blocks[4] = blocks[4].replace(LONG_COMMENT, "# create local currency per USD for comparison against\n# Compustat Global output")

cells, bi = [], 0
for seg in segments:
    if seg.startswith("```python"):
        bi += 1
        cells.append(nbf.v4.new_code_cell(blocks[bi]))
        continue
    parts = re.split(rf"!\[\]\(\.\./images/{IMG}/(\d+)\.png\)", seg)
    for k, part in enumerate(parts):
        if k % 2 == 0:
            if part.strip():
                cells.append(nbf.v4.new_markdown_cell(part.strip()))
        else:
            cells.append(nbf.v4.new_code_cell(IMAGE_CELLS[int(part)]))

too_long = [l for c in cells if c.cell_type == "code" for l in c.source.splitlines() if len(l) > 75]
nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, DEST)
print(f"wrote {os.path.relpath(DEST, ROOT)}: {sum(c.cell_type == 'code' for c in cells)} code cells")
for l in too_long:
    print(f"  long line ({len(l)}): {l}")
