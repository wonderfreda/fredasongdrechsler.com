"""Execute notebooks in place against WRDS and report errors.

Usage (Anaconda python, WRDS username in PGUSER so wrds.Connection() reads ~/.pgpass):
    PGUSER=qsong ~/opt/anaconda3/bin/python _tools/run_notebook.py notebooks/momentum_ciz.ipynb [...]
"""
import os
import sys
import nbformat
from nbclient import NotebookClient

status = 0
for path in sys.argv[1:]:
    nb = nbformat.read(path, as_version=4)
    kernel = nb.metadata.get("kernelspec", {}).get("name", "python3")
    client = NotebookClient(nb, timeout=3600, kernel_name=kernel,
                            resources={"metadata": {"path": os.path.dirname(path) or "."}})
    try:
        client.execute()
    finally:
        nbformat.write(nb, path)
    outs = [o for c in nb.cells for o in c.get("outputs", [])]
    errors = [o for o in outs if o.output_type == "error"]
    warnings = [o for o in outs if o.output_type == "stream" and o.name == "stderr"]
    print(f"{path}: {len(errors)} errors, {len(warnings)} stderr outputs")
    status |= bool(errors)
sys.exit(status)
