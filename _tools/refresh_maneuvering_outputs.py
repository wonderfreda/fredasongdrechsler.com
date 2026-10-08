"""Refresh the output tables on intro-to-python-for-fnce/maneuvering-wrds-data.qmd.

Runs the page's own WRDS code blocks (so outputs always match the code shown) and writes each
output as a Markdown table between marker comments:

    <!-- output:NAME -->
    ...table...
    <!-- /output:NAME -->

Usage (Anaconda python, WRDS username in PGUSER so wrds.Connection() reads ~/.pgpass):
    PGUSER=qsong ~/opt/anaconda3/bin/python _tools/refresh_maneuvering_outputs.py
"""
import os
import re
import wrds

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "intro-to-python-for-fnce", "maneuvering-wrds-data.qmd")
TEXT_COLS = {"conm"}   # names read better left-aligned


def table(df, formats=None):
    """DataFrame -> Markdown table, numbers right-aligned, formatted like the pandas display."""
    df = df.copy()
    for col, fmt in (formats or {}).items():
        df[col] = df[col].map(lambda v: "None" if v is None else fmt.format(v))
    df = df.astype(object).where(df.notna(), "None").astype(str)
    align = ["right"] + ["left" if c in TEXT_COLS else "right" for c in df.columns]
    md = df.to_markdown(index=True, disable_numparse=True, colalign=align)
    return f"::: {{.output-table}}\n{md}\n:::"


def outputs(conn):
    s = open(PAGE).read()
    code = [b for b in re.findall(r"```python\n(.*?)```", s, re.S)
            if "conn." in b and "wrds.Connection" not in b and "list_" not in b]
    env = {"conn": conn}
    for block in code:
        exec(block, env)

    company_narrow, apple, apple_fund = env["company_narrow"], env["apple"], env["apple_fund"]
    apple = apple.assign(mthcaldt=apple["mthcaldt"].dt.strftime("%Y-%m-%d"))
    apple_fund = apple_fund.assign(datadate=apple_fund["datadate"].dt.strftime("%Y-%m-%d"))
    return {
        "company_narrow": table(company_narrow),
        "apple": f"First 12 of the {len(apple)} monthly records returned:\n\n"
                 + table(apple.head(12), {"mthprc": "{:.2f}", "mthret": "{:.6f}"}),
        "apple_fund": f"The {len(apple_fund)} fiscal years returned:\n\n"
                      + table(apple_fund, {"at": "{:.1f}", "prccm": "{:.3f}", "cshoq": "{:.3f}"}),
    }


def main():
    conn = wrds.Connection(verbose=False)
    try:
        new = outputs(conn)
    finally:
        conn.close()
    s = open(PAGE).read()
    for name, body in new.items():
        pattern = re.compile(rf"(<!-- output:{name} -->\n)(?:.*?\n)?(<!-- /output:{name} -->)", re.S)
        assert pattern.search(s), f"marker for {name} not found"
        s = pattern.sub(lambda m: m.group(1) + body + "\n" + m.group(2), s)
    open(PAGE, "w").write(s)
    print("refreshed:", ", ".join(new))


if __name__ == "__main__":
    main()
