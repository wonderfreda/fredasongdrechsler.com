"""Build notebooks/wrds_sec.ipynb from the legacy WRDS SEC page (kept in notebooks/originals/wrds-sec.qmd).

Freda's prose and code are kept; output screenshots become the cells that produce them (the WRDS
website screenshot, an illustration, stays an image). The notebook reads SEC filings from the WRDS
server (/wrds/sec/wrds_clean_filings), so it is executed on wrds-rd. Code formatted with black.
"""
import os
import re
import subprocess
import textwrap
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "notebooks", "originals", "wrds-sec.qmd")
DEST = os.path.join(ROOT, "notebooks", "wrds_sec.ipynb")
UVX = os.path.expanduser("~/.local/bin/uvx")
IMG = "textual-analysis_wrds-sec"

body = open(PAGE).read().split("---", 2)[2]
# WRDS renamed wciklink_names.tickerh to ticker; the rerun returns 14 10-Ks (approved by Freda)
assert body.count("tickerh") == 6
body = body.replace("tickerh", "ticker")
for old, new in [("reduces the sample to 13 records", "reduces the sample to 14 records"),
                 ("the body of the thirteen 10-K filings", "the body of the fourteen 10-K filings")]:
    assert old in body
    body = body.replace(old, new)
segments = re.split(r"(```python\n.*?```)", body, flags=re.S)
blocks = [s[len("```python\n"):-3].rstrip("\n") for s in segments if s.startswith("```python")]
blocks = {i: "\n".join(l.rstrip() for l in b.splitlines()) for i, b in enumerate(blocks, start=1)}
assert len(blocks) == 9

# block 3: the one-line SQL is wrapped so it fits the code box
old = ("footnotes = conn.raw_sql(\"select * from wrdssec_insiders.footnotes "
       "where position('10b5' in text)>0 LIMIT 1000;\")")
assert old in blocks[3]
blocks[3] = blocks[3].replace(old, '''footnotes = conn.raw_sql("""
    select * from wrdssec_insiders.footnotes
    where position('10b5' in text)>0
    LIMIT 1000;
    """)''')

IMAGE_CELLS = {
    1: "cikdf",
    2: "df.head()",
    3: "form.head()",
    4: "# inspect form distribution\nformDist = form.groupby(['form'])['form'].count()\nformDist",
    5: "form10k.head()",
    7: "len(textLst)",
    8: "# first 3,000 characters of the first 10-K (full filing: hundreds of pages)\n"
       "print(textLst[0][:3000])",
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
LONG = "# extract first 1000 observations from insider table that contains '10b5' in text column"
assert LONG in blocks[3]
blocks[3] = blocks[3].replace(LONG, "# extract first 1000 observations from insider table\n# that contains '10b5' in text column")

cells, bi = [], 0
for seg in segments:
    if seg.startswith("```python"):
        bi += 1
        cells.append(nbf.v4.new_code_cell(blocks[bi]))
        continue
    text = re.sub(r'<div class="btn-row">.*?</div>\n*', "", seg, flags=re.S)       # legacy "Full Code" link
    parts = re.split(rf"(!\[\]\(\.\./images/{IMG}/(\d+)\.png\))", text)
    # parts: text, full-image-markdown, number, text, ...
    k = 0
    pending = parts[0]
    while k + 2 < len(parts):
        img_md, num = parts[k + 1], int(parts[k + 2])
        if num in IMAGE_CELLS:
            if pending.strip():
                cells.append(nbf.v4.new_markdown_cell(pending.strip()))
            cells.append(nbf.v4.new_code_cell(IMAGE_CELLS[num]))
            pending = parts[k + 3]
        else:  # illustration: keep the image in the text
            pending = pending + img_md + parts[k + 3]
        k += 3
    if pending.strip():
        cells.append(nbf.v4.new_markdown_cell(pending.strip()))

too_long = [l for c in cells if c.cell_type == "code" for l in c.source.splitlines() if len(l) > 75]
nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, DEST)
print(f"wrote {os.path.relpath(DEST, ROOT)}: {sum(c.cell_type == 'code' for c in cells)} code cells")
for l in too_long:
    print(f"  long line ({len(l)}): {l}")
