"""Refresh the sample output on intro-to-python-for-fnce/sp500-constituents.qmd.

Runs the page's own code blocks against WRDS and writes 10 randomly drawn rows of the final
data frame (fixed seed, so a refresh does not reshuffle them) between the marker comments
<!-- output:sp500ccm --> ... <!-- /output:sp500ccm -->.

Usage: PGUSER=qsong ~/opt/anaconda3/bin/python _tools/refresh_sp500_outputs.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refresh_maneuvering_outputs import table  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "intro-to-python-for-fnce", "sp500-constituents.qmd")
DATE_COLS = ["mthcaldt", "mbrstartdt", "mbrenddt"]


def main():
    s = open(PAGE).read()
    env = {}
    for block in re.findall(r"```python\n(.*?)```", s, re.S):
        exec(block, env)
    env["conn"].close()

    out = env["sp500ccm"]
    sample = out.sample(10, random_state=2026).sort_values(["mthcaldt", "permno"]).reset_index(drop=True)
    for c in DATE_COLS:
        sample[c] = sample[c].dt.strftime("%Y-%m-%d")
    body = (f"10 randomly drawn rows of the {len(out):,} in sp500ccm "
            f"({out.mthcaldt.min():%b %Y}–{out.mthcaldt.max():%b %Y}):\n\n"
            + table(sample, {"mthret": "{:.6f}"})
            .replace("::: {.output-table}", "::: {.output-table .wide .column-page}", 1))

    pattern = re.compile(r"(<!-- output:sp500ccm -->\n)(?:.*?\n)?(<!-- /output:sp500ccm -->)", re.S)
    assert pattern.search(s), "marker not found"
    s = pattern.sub(lambda m: m.group(1) + body + "\n" + m.group(2), s)
    open(PAGE, "w").write(s)
    print("refreshed: sp500ccm")


if __name__ == "__main__":
    main()
